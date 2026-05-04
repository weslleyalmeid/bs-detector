from operator import add
from typing import Annotated, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from agents import check_consistency, score_findings, verify_citations, write_memo
from utils import stable_id, to_case_documents
from schemas import (
    CaseDocument,
    CitationCandidate,
    CitationReview,
    Decision,
    Finding,
    VerificationCheck,
    VerificationReport,
)

CASE_NAME = "Rivera v. Harmon Construction Group, Inc."

_DECISION_BY_TYPE: dict[str, Decision] = {
    "could_not_verify": "unable_to_determine",
    "fact_contradiction": "rejected",
    "inaccurate_quote": "rejected",
    "unsupported_citation": "rejected",
    "claim_supported": "accepted",
}


class State(TypedDict, total=False):
    documents: list[CaseDocument]
    motion: Optional[CaseDocument]
    errors: Annotated[list[str], add]
    citations: list[CitationCandidate]
    findings: list[Finding]
    scored_findings: list[Finding]
    judicial_memo: Optional[str]
    report: Optional[VerificationReport]


def _safe(name, fn):
    def wrapped(state: State) -> dict:
        try:
            return fn(state)
        except Exception as e:  # noqa: BLE001
            return {"errors": [f"[{name}] {type(e).__name__}: {e}"]}
    return wrapped


def _aggregate_decision(decisions: list[Decision]) -> Decision:
    """Worst-case rollup. rejected > unable_to_determine > accepted."""
    if "rejected" in decisions:
        return "rejected"
    if "unable_to_determine" in decisions:
        return "unable_to_determine"
    return "accepted"


def _to_check(f: Finding) -> VerificationCheck:
    return VerificationCheck(
        check_id=stable_id("chk", f.finding_id),
        category=f.category,
        statement=f.statement,
        decision=_DECISION_BY_TYPE.get(f.finding_type, "unable_to_determine"),
        reason=f.assessment,
        source_document=f.source_document,
        evidence_quote=f.evidence_quote,
        confidence=f.confidence,
        confidence_reason=f.confidence_reason,
    )


def _build_citation_review(citations: list[CitationCandidate]) -> CitationReview:
    """Aggregate per-citation support/quote decisions into the review block."""
    if not citations:
        return CitationReview(
            decision="unable_to_determine",
            total_citations=0,
            reason="No legal citations were extracted from the motion.",
            citations=[],
        )

    decisions: list[Decision] = []
    for c in citations:
        decisions.append(c.support_decision)
        if c.quote_decision is not None:
            decisions.append(c.quote_decision)
    overall = _aggregate_decision(decisions)

    rejected = sum(1 for c in citations if c.support_decision == "rejected")

    if overall == "rejected":
        reason = (
            f"{rejected} of {len(citations)} citations have unsupported propositions"
            " or inaccurate quotes."
        )
    elif overall == "unable_to_determine":
        reason = (
            "The motion contains legal citations, but the cited authority texts were"
            " not included in the provided case file."
        )
    else:
        reason = "All citations appear supported by the available record."

    return CitationReview(
        decision=overall,
        total_citations=len(citations),
        reason=reason,
        citations=citations,
    )


# --------------------------- Nodes ---------------------------
# Topology:
#
#   START ─┬─→ citations ──┐
#          │               ├─→ score → memo → assemble → END
#          └─→ consistency ┘


def node_citations(state: State) -> dict:
    motion = state.get("motion")
    if not motion:
        return {}
    authorities = [d for d in state["documents"] if d.document_type == "legal_authority"]
    return {"citations": verify_citations(motion, authorities)}


def node_consistency(state: State) -> dict:
    motion = state.get("motion")
    if not motion:
        return {}
    supporting = [d for d in state["documents"] if d.document_type not in {"motion", "legal_authority"}]
    return {"findings": check_consistency(motion, supporting)}


def node_score(state: State) -> dict:
    scored = score_findings(state.get("findings", []), state.get("documents", []))
    return {"scored_findings": scored}


def node_memo(state: State) -> dict:
    findings = state.get("scored_findings", [])
    try:
        return {"judicial_memo": write_memo(findings)}
    except Exception as e:  # noqa: BLE001
        return {
            "judicial_memo": None,
            "errors": [f"[judicial_memo] {type(e).__name__}: {e}"],
        }


def node_assemble(state: State) -> dict:
    findings = state.get("scored_findings", [])
    citations = state.get("citations", [])
    errors = list(state.get("errors", []))

    citation_review = _build_citation_review(citations)
    fact_findings = [f for f in findings if f.category == "fact"]
    checks = [_to_check(f) for f in fact_findings]
    overall = _aggregate_decision([c.decision for c in checks] + [citation_review.decision])

    rejected = sum(1 for c in checks if c.decision == "rejected")
    accepted = sum(1 for c in checks if c.decision == "accepted")
    unable = sum(1 for c in checks if c.decision == "unable_to_determine")
    summary = (
        f"Overall: {overall}. {len(checks)} factual check(s) — {rejected} rejected,"
        f" {accepted} accepted, {unable} unable to determine. {len(citations)} citation(s)"
        f" reviewed ({citation_review.decision})."
    )

    return {
        "report": VerificationReport(
            case_name=CASE_NAME,
            overall_decision=overall,
            summary=summary,
            citation_review=citation_review,
            checks=checks,
            judicial_memo=state.get("judicial_memo"),
            metrics={
                "total_citations": len(citations),
                "total_checks": len(checks),
                "rejected_count": rejected,
                "unable_to_determine_count": unable,
                "accepted_count": accepted,
            },
            errors=errors,
        )
    }


# --------------------------- Pipeline class ---------------------------


class LegalVerificationAgents:
    """Multi-agent legal verification system.

    Orchestrates citation verification and fact consistency in parallel, then
    runs deterministic confidence scoring, the judicial memo agent, and final
    report assembly in sequence.
    """

    def __init__(self) -> None:
        g: StateGraph = StateGraph(State)
        g.add_node("citations", _safe("citations", node_citations))
        g.add_node("consistency", _safe("consistency", node_consistency))
        g.add_node("score", _safe("score", node_score))
        g.add_node("memo", _safe("memo", node_memo))
        g.add_node("assemble", _safe("assemble", node_assemble))

        g.add_edge(START, "citations")
        g.add_edge(START, "consistency")
        g.add_edge("citations", "score")
        g.add_edge("consistency", "score")
        g.add_edge("score", "memo")
        g.add_edge("memo", "assemble")
        g.add_edge("assemble", END)
        self._graph = g.compile()

    def invoke(self, raw_documents: dict[str, str]) -> VerificationReport:
        documents = to_case_documents(raw_documents)
        motion = next((d for d in documents if d.document_type == "motion"), None)
        final = self._graph.invoke({"documents": documents, "motion": motion})
        report = final.get("report")
        if report:
            return report
        return VerificationReport(
            case_name=CASE_NAME,
            overall_decision="unable_to_determine",
            summary="Pipeline failed before producing a report.",
            citation_review=CitationReview(
                decision="unable_to_determine", total_citations=0, reason="Pipeline failure.", citations=[]
            ),
            errors=final.get("errors", ["Unknown failure."]),
        )


agents = LegalVerificationAgents()
