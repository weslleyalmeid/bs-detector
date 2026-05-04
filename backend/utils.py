"""Adapters + helpers for documents. Deterministic, no LLM."""

import hashlib
import re

from schemas import CaseDocument

_TYPES = {
    "motion": "motion",
    "police": "police_report",
    "medical": "medical_records",
    "witness": "witness_statement",
}


def _classify(stem: str) -> tuple[str, str]:
    lower = stem.lower()
    for key, dtype in _TYPES.items():
        if key in lower:
            return (dtype, dtype)
    return (stem, "other")


def to_case_documents(raw: dict[str, str]) -> list[CaseDocument]:
    """Convert {stem: text} (the existing load_documents shape) to CaseDocument list."""
    docs = []
    for stem, text in raw.items():
        doc_id, dtype = _classify(stem)
        docs.append(
            CaseDocument(document_id=doc_id, document_type=dtype, filename=f"{stem}.txt", text=text)
        )
    return docs


def stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1("||".join(parts).encode()).hexdigest()[:10]
    return f"{prefix}_{digest}"


_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    return _WS.sub(" ", text).strip().lower()


def quote_grounded_in(quote: str, documents: list[CaseDocument]) -> bool:
    if not quote:
        return False
    needle = normalize(quote)
    return any(needle in normalize(d.text) for d in documents)
