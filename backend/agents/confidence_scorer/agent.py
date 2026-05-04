from schemas import CaseDocument, Finding
from utils import quote_grounded_in

# Deterministic confidence rules:
# - could_not_verify is capped at 0.5.
# - GROUNDING_REQUIRED types: floored at 0.8 when the evidence_quote
#   appears verbatim in the source document, capped at 0.4 otherwise.
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
