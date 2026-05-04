from typing import Literal, Optional, Union

from pydantic import BaseModel, Field

DocType = Literal[
    "motion", "police_report", "medical_records", "witness_statement", "legal_authority", "other"
]

Decision = Literal["accepted", "rejected", "unable_to_determine"]
CheckCategory = Literal["citation", "quote", "fact"]
Severity = Literal["low", "medium", "high"]

InternalFindingType = Literal[
    "unsupported_citation",
    "inaccurate_quote",
    "fact_contradiction",
    "claim_supported",
    "could_not_verify",
]


class CaseDocument(BaseModel):
    document_id: str
    document_type: DocType
    filename: str
    text: str


class CitationCandidate(BaseModel):
    citation_id: str
    raw_citation: str
    proposition: str
    direct_quote: Optional[str] = None
    support_decision: Decision = "unable_to_determine"
    support_reason: str = ""
    quote_decision: Optional[Decision] = None
    quote_reason: Optional[str] = None


class Finding(BaseModel):
    finding_id: str
    finding_type: InternalFindingType
    category: CheckCategory
    severity: Severity
    statement: str
    assessment: str
    source_document: Optional[str] = None
    evidence_quote: Optional[str] = None
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    confidence_reason: str = ""


class VerificationCheck(BaseModel):
    check_id: str
    category: CheckCategory
    statement: str
    decision: Decision
    reason: str
    source_document: Optional[str] = None
    evidence_quote: Optional[str] = None
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    confidence_reason: str = ""


class CitationReview(BaseModel):
    decision: Decision
    total_citations: int
    reason: str
    citations: list[CitationCandidate] = Field(default_factory=list)


class VerificationReport(BaseModel):
    case_name: str
    overall_decision: Decision
    summary: str
    citation_review: CitationReview
    checks: list[VerificationCheck] = Field(default_factory=list)
    judicial_memo: Optional[str] = None
    metrics: dict[str, Union[int, float]] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
