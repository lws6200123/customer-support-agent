from __future__ import annotations

from pathlib import Path

from scripts.audit_agent_benchmark import load_benchmark, sha256_file
from scripts.audit_agent_holdout import (
    EXPECTED_INTENT_DISTRIBUTION,
    HOLDOUT_PATH,
    audit_holdout,
)
from scripts.run_agent_holdout import write_holdout_report


def test_holdout_passes_deterministic_audit(tmp_path: Path) -> None:
    database = tmp_path / "holdout.db"
    report = tmp_path / "holdout-audit.md"
    document, errors, summary = audit_holdout(HOLDOUT_PATH, database, report)
    assert not errors
    assert len(document["cases"]) == 24
    assert summary["intent_distribution"] == dict(sorted(EXPECTED_INTENT_DISTRIBUTION.items()))
    assert summary["escalation_critical"] == 6
    assert summary["information_missing"] == 5
    assert report.read_text(encoding="utf-8").startswith(
        "# Stage 8A Post-fix Holdout Audit"
    )


def test_holdout_messages_are_exactly_disjoint_from_main_benchmark() -> None:
    holdout = load_benchmark(HOLDOUT_PATH)
    benchmark = load_benchmark()
    holdout_messages = {case["message"] for case in holdout["cases"]}
    benchmark_messages = {case["message"] for case in benchmark["cases"]}
    assert len(holdout_messages) == 24
    assert holdout_messages.isdisjoint(benchmark_messages)
    assert sha256_file(HOLDOUT_PATH) == "0eb3da3ef0b8012a3f69c06a938d5f87152092ae1fe481a3cc273774dd1c9252"


def test_holdout_report_declares_no_subsequent_tuning(tmp_path: Path) -> None:
    path = tmp_path / "holdout-report.md"
    metrics = {
        "case_count": 1,
        "intent_accuracy": 1.0,
        "intent_correct": 1,
        "decision_accuracy": 1.0,
        "decision_correct": 1,
        "task_success_rate": 1.0,
        "task_success_count": 1,
        "escalation": {"precision": None, "recall": None, "f1": None},
        "tools": {"precision": 1.0, "recall": 1.0, "f1": 1.0, "exact_set_accuracy": 1.0},
        "average_tool_calls": 0.0,
        "system_error_rate": 0.0,
        "system_error_count": 0,
        "latency_ms": {"mean": 1.0, "p50": 1.0, "p95": 1.0, "min": 1.0, "max": 1.0},
    }
    metadata = {
        "run_id": "TEST",
        "holdout_sha256": "digest",
        "system_freeze_commit": "commit",
        "deepseek_model": "model",
        "intent_distribution": {"OTHER": 1},
        "decision_distribution": {"AUTO_RESOLVE": 1},
        "escalation_critical": 0,
        "information_missing": 0,
    }
    write_holdout_report([], metrics, metadata, path)
    text = path.read_text(encoding="utf-8")
    assert "created and frozen after the Stage 8A fixes" in text
    assert "not used for subsequent system tuning" in text
