"""Tool-call schema for the CitationVerifier agent."""

from typing import Optional

from pydantic import BaseModel, Field

from schemas import Decision

AUTHORITY_MISSING_SUPPORT = (
    "The cited authority text was not available in the provided case file."
)
AUTHORITY_MISSING_QUOTE = (
    "The quoted authority text was not available for direct comparison."
)


class CitItem(BaseModel):
    raw_citation: str
    proposition: str
    direct_quote: Optional[str] = None
    support_decision: Decision = "unable_to_determine"
    support_reason: str = ""
    quote_decision: Optional[Decision] = None
    quote_reason: Optional[str] = None


class CitOut(BaseModel):
    items: list[CitItem] = Field(default_factory=list)
