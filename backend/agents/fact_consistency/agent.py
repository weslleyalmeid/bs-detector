import re

from llm import call_with_tool
from schemas import CaseDocument, Finding, InternalFindingType
from utils import normalize, stable_id

from .prompt import FACT_PROMPT
from .schema import FactItem, FactOut

_GROUNDED_TYPES = {"fact_contradiction", "claim_supported"}
_DECISION_RANK = {"fact_contradiction": 0, "claim_supported": 1, "could_not_verify": 2}

_DATE_RE = re.compile(r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:,\s*\d{4})?\b", re.I)
_NUMBER_RE = re.compile(r"\b\d{2,}\b")
_PROPER_RE = re.compile(r"\b[A-Z][a-z]{2,}\b")
_STOPWORDS = {"the", "and", "for", "with", "from", "that", "this", "was", "were"}


def check_consistency(motion: CaseDocument, supporting: list[CaseDocument]) -> list[Finding]:
    if not supporting:
        return []
    corpus = "\n\n---\n\n".join(
        f"[{d.document_id} | {d.filename}]\n{d.text}" for d in supporting
    )

    out = call_with_tool(
        messages=[
            {"role": "system", "content": FACT_PROMPT},
            {
                "role": "user",
                "content": f"MOTION:\n{motion.text}\n\nSUPPORTING DOCUMENTS:\n{corpus}",
            },
        ],
        schema=FactOut,
        tool_name="emit_consistency_findings",
        tool_description="Emit cross-document fact-consistency findings.",
    )

    findings = [_to_finding(item) for item in out.items]
    return _dedupe(findings)


def _salient_tokens(text: str) -> set[str]:
    if not text:
        return set()
    raw = " ".join(_DATE_RE.findall(text))
    raw += " " + " ".join(_NUMBER_RE.findall(text))
    raw += " " + " ".join(_PROPER_RE.findall(text))
    tokens = {normalize(t) for t in raw.split() if t}
    return {t for t in tokens if t and t not in _STOPWORDS and len(t) > 2}


def _to_finding(item: FactItem) -> Finding:
    finding_type: InternalFindingType = item.finding_type
    assessment = item.assessment
    source = item.source_document
    quote = item.evidence_quote

    # Safeguard 1: missing source/quote downgrade.
    if finding_type in _GROUNDED_TYPES and (not source or not quote):
        finding_type = "could_not_verify"
        source, quote = None, None
        assessment = (
            f"{assessment} (downgraded: agent returned {item.finding_type} without"
            " a verbatim source quote.)"
        ).strip()

    # Safeguard 2: semantic grounding via salient-token overlap.
    if finding_type in _GROUNDED_TYPES:
        stmt_tokens = _salient_tokens(item.statement)
        quote_tokens = _salient_tokens(quote or "")
        if stmt_tokens and not (stmt_tokens & quote_tokens):
            finding_type = "could_not_verify"
            assessment = (
                f"{assessment} (downgraded: evidence quote did not share a salient"
                " token with the statement.)"
            ).strip()
            source, quote = None, None

    return Finding(
        finding_id=stable_id("fnd", "fact", item.statement, finding_type),
        finding_type=finding_type,
        category="fact",
        severity=item.severity,
        statement=item.statement,
        assessment=assessment,
        source_document=source,
        evidence_quote=quote,
        confidence=0.6,
    )


def _signature(f: Finding) -> frozenset[str]:
    """Salient-token signature used to detect duplicate claims."""
    tokens = _salient_tokens(f.statement)
    if not tokens:
        return frozenset({normalize(f.statement)[:80]})
    return frozenset(tokens)


def _dedupe(findings: list[Finding]) -> list[Finding]:
    """Keep the strongest finding per signature: rejected > accepted > could_not_verify."""
    by_sig: dict[frozenset[str], Finding] = {}
    for f in findings:
        sig = _signature(f)
        current = by_sig.get(sig)
        if current is None or _DECISION_RANK[f.finding_type] < _DECISION_RANK[current.finding_type]:
            by_sig[sig] = f
    return list(by_sig.values())
