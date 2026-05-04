"""JudicialMemo agent.

Free-text summarizer: takes the ranked Findings and produces a short paragraph
suitable for a judge. Uses plain chat completion (no tool call) since the
output is prose, not structured data.
"""

from llm import call_llm
from schemas import Finding

from .prompt import MEMO_PROMPT

_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}
_TOP_N = 8


def write_memo(findings: list[Finding]) -> str | None:
    if not findings:
        return None
    top = sorted(
        findings, key=lambda f: (_SEVERITY_RANK.get(f.severity, 3), -f.confidence)
    )[:_TOP_N]
    body = "\n".join(_format(f) for f in top)
    text = call_llm(
        [{"role": "system", "content": MEMO_PROMPT}, {"role": "user", "content": body}]
    ).strip()
    return text or None


def _format(f: Finding) -> str:
    line = f"- [{f.severity}|{f.finding_type}] {f.statement}\n  {f.assessment}"
    if f.evidence_quote:
        line += f'\n  evidence ({f.source_document}): "{f.evidence_quote}"'
    return line
