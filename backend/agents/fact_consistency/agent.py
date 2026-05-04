"""FactConsistency agent.

Compares factual claims in the Motion against supporting documents (police
report, medical records, witness statement) and returns Finding objects.
"""

from llm import call_with_tool
from schemas import CaseDocument, Finding
from utils import stable_id

from .prompt import FACT_PROMPT
from .schema import FactOut


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

    return [
        Finding(
            finding_id=stable_id("fnd", "fact", item.statement, item.finding_type),
            finding_type=item.finding_type,
            category="fact",
            severity=item.severity,
            statement=item.statement,
            assessment=item.assessment,
            source_document=item.source_document,
            evidence_quote=item.evidence_quote,
            confidence=0.6,
        )
        for item in out.items
    ]
