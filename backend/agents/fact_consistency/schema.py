"""Tool-call schema for the FactConsistency agent."""

from typing import Optional

from pydantic import BaseModel, Field

from schemas import InternalFindingType, Severity


class FactItem(BaseModel):
    finding_type: InternalFindingType
    severity: Severity
    statement: str
    assessment: str
    source_document: Optional[str] = None
    evidence_quote: Optional[str] = None


class FactOut(BaseModel):
    items: list[FactItem] = Field(default_factory=list)
