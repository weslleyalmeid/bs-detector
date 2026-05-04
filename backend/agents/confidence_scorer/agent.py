"""ConfidenceScoringAgent.

Deterministic scoring layer (no LLM). Normalizes confidence values and
attaches a human-readable confidence_reason to each finding so the public
report always tells the reader *why* a confidence is what it is.

Rules:
- could_not_verify is capped at 0.5.
- fact_contradiction / claim_supported / inaccurate_quote require their
  evidence_quote to appear verbatim in the named source document. When
  grounded, confidence is floored at 0.8; when ungrounded, capped at 0.4.
"""

from schemas import CaseDocument, Finding
from utils import quote_grounded_in

GROUNDING_REQUIRED = {"fact_contradiction", "inaccurate_quote", "claim_supported"}


def score_findings(findings: list[Finding], documents: list[CaseDocument]) -> list[Finding]:
    return [_score_one(f, documents) for f in findings]


def _score_one(f: Finding, documents: list[CaseDocument]) -> Finding:
    conf, reason = f.confidence, f.confidence_reason

    if f.finding_type == "could_not_verify":
        conf = min(conf, 0.5)
        if not reason:
            reason = (
                "Evidence available but insufficient to confirm or refute the claim."
                if (f.source_document and f.evidence_quote)
                else "Required evidence was not available in the case file."
            )
    elif f.finding_type in GROUNDING_REQUIRED:
        grounded = quote_grounded_in(f.evidence_quote or "", documents)
        if grounded:
            conf = max(conf, 0.8)
            reason = (reason + " Evidence quote located verbatim in source document.").strip()
        else:
            conf = min(conf, 0.4)
            reason = (reason + " Lowered: evidence quote not found verbatim.").strip()

    return f.model_copy(update={"confidence": round(conf, 2), "confidence_reason": reason})
