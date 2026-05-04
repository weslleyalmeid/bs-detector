import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS.parent))

from main import load_documents  # noqa: E402
from pipeline import agents  # noqa: E402
from schemas import CitationCandidate, VerificationCheck, VerificationReport  # noqa: E402
from utils import normalize, quote_grounded_in, to_case_documents  # noqa: E402

GOLDEN_PATH = THIS / "golden_findings.json"
BASELINE_PATH = THIS / "baseline_results.json"
RUNS_DIR = THIS / "runs"


def _check_text(check: VerificationCheck) -> str:
    return normalize(
        " ".join([check.statement or "", check.reason or "", check.evidence_quote or ""])
    )


def _citation_text(c: CitationCandidate) -> str:
    return normalize(
        " ".join(
            [
                c.raw_citation or "",
                c.proposition or "",
                c.direct_quote or "",
                c.support_reason or "",
                c.quote_reason or "",
            ]
        )
    )


def _keyword_overlap(text: str, keywords: Iterable[str]) -> bool:
    return any(normalize(kw) in text for kw in keywords if kw)


def _source_compatible(expected_source: str | None, generated_source: str | None) -> bool:
    if not expected_source:
        return True
    if not generated_source:
        return False
    return normalize(expected_source) in normalize(generated_source) or normalize(
        generated_source
    ) in normalize(expected_source)


def _match_check(expected: dict, check: VerificationCheck) -> bool:
    if check.category != expected["category"]:
        return False
    if check.decision != expected["expected_decision"]:
        return False
    if not _source_compatible(expected.get("expected_source_document"), check.source_document):
        return False
    text = _check_text(check)
    keywords = list(expected.get("statement_keywords", [])) + list(
        expected.get("evidence_keywords", [])
    )
    return _keyword_overlap(text, keywords)


def _match_citation(expected: dict, citation: CitationCandidate) -> bool:
    decisions = {citation.support_decision}
    if citation.quote_decision is not None:
        decisions.add(citation.quote_decision)
    if expected["expected_decision"] not in decisions:
        return False
    text = _citation_text(citation)
    keywords = list(expected.get("statement_keywords", [])) + list(
        expected.get("evidence_keywords", [])
    )
    return _keyword_overlap(text, keywords)


def score(report: VerificationReport, golden: dict) -> dict:
    expected_checks = golden["expected_checks"]
    docs = to_case_documents(load_documents())

    used_checks: set[str] = set()
    used_citations: set[str] = set()
    matched_total = 0
    matched_rejected = 0
    expected_rejected = 0

    for exp in expected_checks:
        if exp["expected_decision"] == "rejected":
            expected_rejected += 1

        hit = False
        if exp["category"] == "fact":
            for c in report.checks:
                if c.check_id in used_checks:
                    continue
                if _match_check(exp, c):
                    used_checks.add(c.check_id)
                    hit = True
                    break
        else:
            for cit in report.citation_review.citations:
                if cit.citation_id in used_citations:
                    continue
                if _match_citation(exp, cit):
                    used_citations.add(cit.citation_id)
                    hit = True
                    break

        if hit:
            matched_total += 1
            if exp["expected_decision"] == "rejected":
                matched_rejected += 1

    generated_rejected = [c for c in report.checks if c.decision == "rejected"]
    correct_rejected = sum(1 for c in generated_rejected if c.check_id in used_checks)

    ungrounded_rejected = 0
    for c in generated_rejected:
        if (
            not c.evidence_quote
            or not c.source_document
            or not quote_grounded_in(c.evidence_quote, docs)
        ):
            ungrounded_rejected += 1

    total_checks = len(report.checks)
    accepted_checks = sum(1 for c in report.checks if c.decision == "accepted")
    unable_checks = sum(1 for c in report.checks if c.decision == "unable_to_determine")
    determined_checks = accepted_checks + len(generated_rejected)

    try:
        VerificationReport.model_validate(report.model_dump())
        schema_validity = 1.0
    except Exception:  # noqa: BLE001
        schema_validity = 0.0

    def _ratio(num: int, den: int) -> float:
        return round(num / den, 3) if den else 0.0

    return {
        "schema_validity": schema_validity,
        "precision": _ratio(correct_rejected, len(generated_rejected)),
        "recall": _ratio(matched_rejected, expected_rejected),
        "hallucination_rate": _ratio(ungrounded_rejected, len(generated_rejected)),
        "unable_to_determine_rate": _ratio(unable_checks, total_checks),
        "coverage": _ratio(determined_checks, total_checks),
        "counts": {
            "expected_total": len(expected_checks),
            "expected_rejected": expected_rejected,
            "matched_expected_total": matched_total,
            "matched_expected_rejected": matched_rejected,
            "generated_rejected": len(generated_rejected),
            "correct_rejected": correct_rejected,
            "ungrounded_rejected": ungrounded_rejected,
            "accepted_checks": accepted_checks,
            "unable_to_determine_checks": unable_checks,
            "total_checks": total_checks,
            "total_citations": len(report.citation_review.citations),
        },
        "overall_decision": report.overall_decision,
    }


def _print_report(metrics: dict) -> None:
    print("\n=== BS Detector Eval Results ===")
    print(f"Schema validity: {metrics['schema_validity']:.2f}")
    print(f"Precision: {metrics['precision']:.2f}")
    print(f"Recall: {metrics['recall']:.2f}")
    print(f"Hallucination rate: {metrics['hallucination_rate']:.2f}")
    print(f"Unable-to-determine rate: {metrics['unable_to_determine_rate']:.2f}")
    print(f"Coverage: {metrics['coverage']:.2f}")
    print("\nCounts:")
    for k, v in metrics["counts"].items():
        print(f"- {k}: {v}")


def _persist(metrics: dict, report: VerificationReport, golden: dict) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = {
        "timestamp": timestamp,
        "case_id": golden.get("case_id"),
        "overall_decision": report.overall_decision,
        "metrics": metrics,
    }
    BASELINE_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    RUNS_DIR.mkdir(exist_ok=True)
    run_path = RUNS_DIR / f"{timestamp}.json"
    run_path.write_text(json.dumps(payload, indent=2) + "\n")
    return run_path


def main() -> int:
    golden = json.loads(GOLDEN_PATH.read_text())
    print("Running pipeline...")
    report = agents.invoke(load_documents())
    metrics = score(report, golden)
    _print_report(metrics)
    run_path = _persist(metrics, report, golden)
    print(f"\nSaved: {BASELINE_PATH.relative_to(THIS.parent)}")
    print(f"       {run_path.relative_to(THIS.parent)}")
    if report.errors:
        print("\nPipeline errors:")
        for e in report.errors:
            print(f"  - {e}")
    return 0 if metrics["schema_validity"] == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
