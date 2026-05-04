"""Tiny eval harness. Runs the pipeline once and scores checks.

Usage (from backend/):
    .venv/bin/python evals/run_evals.py
"""

import json
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS.parent))

from main import load_documents  # noqa: E402
from pipeline import agents  # noqa: E402
from schemas import VerificationReport  # noqa: E402
from utils import normalize, quote_grounded_in, to_case_documents  # noqa: E402

GOLDEN = json.loads((THIS / "golden_findings.json").read_text())


def _matches(expected, check) -> bool:
    if check.category != expected["category"]:
        return False
    if check.decision != expected["decision"]:
        return False
    hay = normalize(f"{check.statement} {check.reason}")
    return any(normalize(kw) in hay for kw in expected["keywords"])


def score(report: VerificationReport) -> dict:
    expected = GOLDEN["expected_checks"]
    matched, used = 0, set()
    for exp in expected:
        for c in report.checks:
            if c.check_id in used:
                continue
            if _matches(exp, c):
                matched += 1
                used.add(c.check_id)
                break

    docs = to_case_documents(load_documents())
    counted = hallucinated = 0
    for c in report.checks:
        # Only "rejected" checks need to be grounded with a verbatim quote.
        if c.decision != "rejected":
            continue
        counted += 1
        if not c.evidence_quote or not c.source_document or not quote_grounded_in(c.evidence_quote, docs):
            hallucinated += 1

    try:
        VerificationReport.model_validate(report.model_dump())
        schema_ok = 1.0
    except Exception:  # noqa: BLE001
        schema_ok = 0.0

    return {
        "expected_total": len(expected),
        "expected_matched": matched,
        "generated_checks": len(report.checks),
        "overall_decision": report.overall_decision,
        "precision": round(matched / len(report.checks), 3) if report.checks else 0.0,
        "recall": round(matched / len(expected), 3) if expected else 0.0,
        "hallucination_rate": round(hallucinated / counted, 3) if counted else 0.0,
        "schema_validity": schema_ok,
    }


def main() -> int:
    print("Running pipeline...")
    report = agents.invoke(load_documents())
    metrics = score(report)
    print("\n=== BS Detector Eval ===")
    print(json.dumps(metrics, indent=2))
    print("\nChecks:")
    for c in report.checks:
        print(f"  - [{c.category}|{c.decision}|conf={c.confidence}] {c.statement}")
    if report.errors:
        print("\nErrors:")
        for e in report.errors:
            print(f"  - {e}")
    return 0 if metrics["schema_validity"] == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
