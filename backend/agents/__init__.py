"""Multi-agent legal verification system.

Each agent is a self-contained subpackage with its own prompt, tool-call
schema, and runner function. The pipeline orchestrates them in a LangGraph
StateGraph.

Roles:
- CitationVerifierAgent  -> agents/citation_verifier
- FactConsistencyAgent   -> agents/fact_consistency
- ConfidenceScoringAgent -> agents/confidence_scorer (deterministic)
- JudicialMemoAgent      -> agents/judicial_memo
"""

from .citation_verifier import verify_citations
from .confidence_scorer import score_findings
from .fact_consistency import check_consistency
from .judicial_memo import write_memo

__all__ = ["verify_citations", "check_consistency", "score_findings", "write_memo"]
