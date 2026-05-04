"""CitationVerifier agent.

Reads the Motion + any legal-authority documents in the case file and returns
one CitationCandidate per citation, each with explicit support/quote decisions.
"""

from typing import Optional

from llm import call_with_tool
from schemas import CaseDocument, CitationCandidate, Decision
from utils import stable_id

from .prompt import CITATION_PROMPT
from .schema import AUTHORITY_MISSING_QUOTE, AUTHORITY_MISSING_SUPPORT, CitItem, CitOut


def verify_citations(
    motion: CaseDocument, authorities: list[CaseDocument]
) -> list[CitationCandidate]:
    corpus = (
        "\n\n---\n\n".join(f"[{d.filename}]\n{d.text}" for d in authorities)
        or "(No authority opinions available in the case file.)"
    )
    have_corpus = bool(authorities)

    out = call_with_tool(
        messages=[
            {"role": "system", "content": CITATION_PROMPT},
            {
                "role": "user",
                "content": f"MOTION:\n{motion.text}\n\nAUTHORITIES CORPUS:\n{corpus}",
            },
        ],
        schema=CitOut,
        tool_name="emit_citations",
        tool_description="Emit extracted citations with support and quote decisions.",
    )

    return [_to_candidate(item, have_corpus) for item in out.items]


def _to_candidate(item: CitItem, have_corpus: bool) -> CitationCandidate:
    cid = stable_id("cit", item.raw_citation, item.proposition[:80])

    if not have_corpus:
        support_decision: Decision = "unable_to_determine"
        support_reason = AUTHORITY_MISSING_SUPPORT
        quote_decision: Optional[Decision] = (
            "unable_to_determine" if item.direct_quote else None
        )
        quote_reason: Optional[str] = AUTHORITY_MISSING_QUOTE if item.direct_quote else None
    else:
        support_decision = item.support_decision
        support_reason = item.support_reason or (
            AUTHORITY_MISSING_SUPPORT if support_decision == "unable_to_determine" else ""
        )
        if item.direct_quote:
            quote_decision = item.quote_decision or "unable_to_determine"
            quote_reason = item.quote_reason or (
                AUTHORITY_MISSING_QUOTE if quote_decision == "unable_to_determine" else ""
            )
        else:
            quote_decision = None
            quote_reason = None

    return CitationCandidate(
        citation_id=cid,
        raw_citation=item.raw_citation,
        proposition=item.proposition,
        direct_quote=item.direct_quote,
        support_decision=support_decision,
        support_reason=support_reason,
        quote_decision=quote_decision,
        quote_reason=quote_reason,
    )
