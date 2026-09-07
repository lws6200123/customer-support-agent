#!/usr/bin/env python3
"""Deterministically audit and freeze the post-fix Stage 8A holdout."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.audit_agent_benchmark import (  # noqa: E402
    BENCHMARK_PATH,
    EVALUATION_DB_PATH,
    load_benchmark,
    prepare_evaluation_database,
    sha256_file,
    validate_benchmark,
)


HOLDOUT_PATH = PROJECT_ROOT / "data" / "evaluation" / "agent_holdout.yaml"
HOLDOUT_AUDIT_REPORT_PATH = PROJECT_ROOT / "reports" / "stage8a_holdout_audit.md"
EXPECTED_CASE_COUNT = 24
EXPECTED_INTENT_DISTRIBUTION = {
    "RETURN_REFUND": 6,
    "DELIVERY": 4,
    "PRODUCT_AFTER_SALES": 4,
    "ACCOUNT": 3,
    "INVOICE": 3,
    "OTHER": 4,
}
FROZEN_STAGE8A_FILES = {
    "data/evaluation/agent_benchmark.yaml": "258400c7fb9bddab2ebc742553b67d3c21bdd5cef50d76f15689c1544419ad10",
    "data/evaluation/results/official_run_1_cases.csv": "d9de539ff6b1966406ba0e16e5804fb717a6595b8baa2a81e28e390497de9885",
    "data/evaluation/results/official_run_1_cases.json": "c359b41f2a8e7f3beae29c0245113892f4e3f55783323d5ab420312c6027930f",
    "data/evaluation/results/official_run_1_metadata.json": "f966b4ab2110a79db94e284faab5a26a1050ff289234db2f7c0bf2f592a0bbef",
    "data/evaluation/results/official_run_1_metrics.json": "9ea261bd066005d4ebbf2b333288a6e9342d34c3ff0e0bf3b3e75ef5810ee304",
    "data/evaluation/results/official_run_2_cases.csv": "80685edfaa90b8b4f77c533d30d38f0b7f2b5672303ed5e552273493d3723714",
    "data/evaluation/results/official_run_2_cases.json": "fd2993a6ff98cff1d5e3d05638756713d06d535d65d414543fad5e2be4a184e8",
    "data/evaluation/results/official_run_2_metadata.json": "2f5b3e9e0e527439231afcffe3c7e914404b43f93099131a2f89ced818cf1b58",
    "data/evaluation/results/official_run_2_metrics.json": "9a2098401e4ba4da6e6951213cb6fc68c09ef48609bd1dc349e0acc9a482a986",
}


def verify_frozen_files(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for relative, expected in FROZEN_STAGE8A_FILES.items():
        path = PROJECT_ROOT / relative
        if not path.is_file() or sha256_file(path) != expected:
            errors.append(f"frozen Stage 8A artifact changed: {relative}")
    freeze = document.get("system_freeze") or {}
    files = freeze.get("files") or {}
    if not isinstance(files, dict) or not files:
        errors.append("system_freeze.files must declare frozen system files")
        return errors
    for relative, expected in files.items():
        path = PROJECT_ROOT / str(relative)
        if not path.is_file() or sha256_file(path) != expected:
            errors.append(f"frozen system file changed: {relative}")
    return errors


def validate_holdout(
    document: dict[str, Any], database_path: Path = EVALUATION_DB_PATH
) -> list[str]:
    errors = validate_benchmark(
        document,
        database_path,
        expected_case_count=EXPECTED_CASE_COUNT,
    )
    cases = document.get("cases") or []
    intent_distribution = Counter(case.get("expected_intent") for case in cases)
    if dict(intent_distribution) != EXPECTED_INTENT_DISTRIBUTION:
        errors.append(
            "intent distribution does not match the frozen 24-case holdout plan"
        )
    decision_distribution = Counter(case.get("expected_decision") for case in cases)
    if not all(decision_distribution.get(name, 0) for name in (
        "AUTO_RESOLVE", "NEED_MORE_INFO", "ESCALATE_TO_HUMAN"
    )):
        errors.append("holdout must cover every decision")
    critical = sum(case.get("risk_class") == "escalation-critical" for case in cases)
    missing = sum(case.get("risk_class") == "information-missing" for case in cases)
    if not 5 <= critical <= 6:
        errors.append("holdout must contain 5-6 escalation-critical cases")
    if not 4 <= missing <= 5:
        errors.append("holdout must contain 4-5 information-missing cases")
    messages = [str(case.get("message") or "").strip() for case in cases]
    if len(messages) != len(set(messages)):
        errors.append("holdout messages must be unique")
    original_messages = {
        str(case.get("message") or "").strip()
        for case in load_benchmark(BENCHMARK_PATH).get("cases", [])
    }
    overlap = sorted(set(messages) & original_messages)
    if overlap:
        errors.append(f"holdout contains {len(overlap)} exact benchmark message duplicates")
    errors.extend(verify_frozen_files(document))
    return errors


def build_summary(document: dict[str, Any], digest: str) -> dict[str, Any]:
    cases = document["cases"]
    return {
        "count": len(cases),
        "intent_distribution": dict(
            sorted(Counter(case["expected_intent"] for case in cases).items())
        ),
        "decision_distribution": dict(
            sorted(Counter(case["expected_decision"] for case in cases).items())
        ),
        "escalation_critical": sum(
            case["risk_class"] == "escalation-critical" for case in cases
        ),
        "information_missing": sum(
            case["risk_class"] == "information-missing" for case in cases
        ),
        "sha256": digest,
    }


def write_holdout_audit_report(
    summary: dict[str, Any], errors: list[str], path: Path = HOLDOUT_AUDIT_REPORT_PATH
) -> None:
    lines = [
        "# Stage 8A Post-fix Holdout Audit",
        "",
        f"**Status: {'PASS' if not errors else 'FAIL'}**",
        "",
        f"- Cases: {summary['count']}",
        f"- Intent distribution: `{summary['intent_distribution']}`",
        f"- Decision distribution: `{summary['decision_distribution']}`",
        f"- Escalation-critical: {summary['escalation_critical']}",
        f"- Information-missing: {summary['information_missing']}",
        f"- Holdout SHA256: `{summary['sha256']}`",
        "- Identifier, enum, taxonomy, tool conflict, deterministic refund, exact-message disjointness, and secret checks: completed",
        "- Frozen Stage 8A artifacts and frozen system source hashes: verified",
        "",
        "This holdout was created and frozen after the Stage 8A fixes and was not used for subsequent system tuning.",
        "",
        "## Errors",
        "",
    ]
    lines.extend([f"- {error}" for error in errors] or ["No audit errors."])
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def audit_holdout(
    holdout_path: Path = HOLDOUT_PATH,
    database_path: Path = EVALUATION_DB_PATH,
    report_path: Path = HOLDOUT_AUDIT_REPORT_PATH,
) -> tuple[dict[str, Any], list[str], dict[str, Any]]:
    document = load_benchmark(holdout_path)
    prepare_evaluation_database(document, database_path)
    errors = validate_holdout(document, database_path)
    summary = build_summary(document, sha256_file(holdout_path))
    write_holdout_audit_report(summary, errors, report_path)
    return document, errors, summary


def main() -> int:
    _, errors, summary = audit_holdout()
    print(f"Stage 8A holdout audit: {'PASS' if not errors else 'FAIL'}")
    print(f"Cases: {summary['count']}")
    print(f"SHA256: {summary['sha256']}")
    print(f"Report: {HOLDOUT_AUDIT_REPORT_PATH}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
