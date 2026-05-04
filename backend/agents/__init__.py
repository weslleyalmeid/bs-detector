"""Multi-agent legal verification system.

Each agent is a self-contained subpackage with its own prompt, tool-call
schema, and runner function. The pipeline orchestrates them in a LangGraph
StateGraph.
"""

from .citation_verifier import verify_citations
from .fact_consistency import check_consistency
from .judicial_memo import write_memo

__all__ = ["verify_citations", "check_consistency", "write_memo"]
