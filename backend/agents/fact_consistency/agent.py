"""FactConsistency agent.

Compares factual claims in the Motion against supporting documents (police
report, medical records, witness statement) and returns Finding objects.
"""

from llm import call_with_tool
from schemas import CaseDocument, Finding
from utils import stable_id

from .prompt import FACT_PROMPT
from .schema import FactItem, FactOut

# A grounded finding must name a source document AND a quote.
_GROUNDED_TYPES = {"fact_contradiction", "claim_supported"}


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

    return [_to_finding(item) for item in out.items]


def _to_finding(item: FactItem) -> Finding:
    finding_type = item.finding_type
    assessment = item.assessment
    source = item.source_document
    quote = item.evidence_quote

    # Defensive downgrade: a grounded decision without source+quote is not
    # actually grounded. Demote to could_not_verify so it cannot be flagged
    # as a rejection / hallucination.
    if finding_type in _GROUNDED_TYPES and (not source or not quote):
        finding_type = "could_not_verify"
        source = None
        quote = None
        assessment = (
            f"{assessment} (downgraded: agent returned {item.finding_type} without"
            " a verbatim source quote.)"
        ).strip()

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

