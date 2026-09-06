from __future__ import annotations

from datetime import datetime
from pathlib import Path

from customer_support_agent.agent.schemas import AgentAction, AgentRunStatus, Intent, ToolExecutionRecord
from customer_support_agent.core.schemas import Decision
from scripts.audit_agent_benchmark import BENCHMARK_PATH, audit_benchmark, load_benchmark
from scripts.run_agent_benchmark import classify_failures, compute_metrics, evaluate_case


def _row(**updates):  # type: ignore[no-untyped-def]
    base = {
        "case_id": "CASE-1",
        "expected_intent": "DELIVERY",
        "predicted_intent": "DELIVERY",
        "expected_decision": "AUTO_RESOLVE",
        "predicted_decision": "AUTO_RESOLVE",
        "required_tools": ["lookup_order"],
        "allowed_optional_tools": ["search_knowledge"],
        "actual_tool_sequence": ["lookup_order", "search_knowledge"],
        "tool_exact_match": False,
        "intent_correct": True,
        "decision_correct": True,
        "task_success": True,
        "tool_call_count": 2,
        "latency_ms": 100.0,
        "system_error": False,
        "primary_failure": None,
        "risk_class": "normal",
    }
    return {**base, **updates}


def test_official_benchmark_passes_deterministic_audit(tmp_path: Path) -> None:
    database = tmp_path / "evaluation.db"
    report = tmp_path / "audit.md"
    document, errors, summary = audit_benchmark(BENCHMARK_PATH, database, report)
    assert not errors
    assert len(document["cases"]) == 60
    assert summary["escalation_critical"] >= 10
    assert summary["information_missing"] >= 8
    assert report.read_text(encoding="utf-8").startswith("# Stage 8A Benchmark Audit")


def test_benchmark_contains_expected_intent_distribution() -> None:
    cases = load_benchmark()["cases"]
    distribution = {intent: sum(case["expected_intent"] == intent for case in cases) for intent in {case["expected_intent"] for case in cases}}
    assert distribution == {
        "RETURN_REFUND": 15,
        "DELIVERY": 10,
        "PRODUCT_AFTER_SALES": 10,
        "ACCOUNT": 8,
        "INVOICE": 8,
        "OTHER": 9,
    }


def test_tool_metrics_treat_optional_tools_as_neutral() -> None:
    metrics = compute_metrics([_row()])
    assert metrics["tools"]["precision"] == 1.0
    assert metrics["tools"]["recall"] == 1.0
    assert metrics["tools"]["exact_set_accuracy"] == 0.0


def test_metric_zero_denominator_is_na() -> None:
    metrics = compute_metrics([])
    assert metrics["intent_accuracy"] is None
    assert metrics["escalation"]["precision"] is None
    assert metrics["tools"]["precision"] is None


def test_expected_not_found_tool_result_is_not_a_failure_category() -> None:
    row = {
        "task_success": True,
        "error_codes": ["ORDER_NOT_FOUND"],
        "system_error": False,
        "knowledge_retrieval_success": True,
        "actual_tool_sequence": ["lookup_order"],
        "tool_results": [{"tool": "lookup_order", "ok": False, "error_code": "ORDER_NOT_FOUND"}],
        "intent_correct": True,
        "required_tools_satisfied": True,
        "unexpected_tools": [],
        "missing_fields_correct": True,
        "decision_correct": True,
        "expected_decision": "NEED_MORE_INFO",
    }
    assert classify_failures(row) == (None, [])


def test_system_error_cannot_count_as_task_success() -> None:
    case = {
        "case_id": "SYSTEM-ERROR",
        "risk_class": "normal",
        "expected_intent": "DELIVERY",
        "expected_decision": "ESCALATE_TO_HUMAN",
        "required_tools": ["search_knowledge"],
        "allowed_optional_tools": [],
        "forbidden_tools": [],
        "expected_missing_fields": [],
    }
    state = {
        "intent": Intent.DELIVERY,
        "decision": Decision.ESCALATE_TO_HUMAN,
        "run_status": AgentRunStatus.ESCALATED,
        "tool_results": [
            ToolExecutionRecord(
                action=AgentAction.SEARCH_KNOWLEDGE,
                tool_name="search_knowledge",
                ok=False,
                error_code="KNOWLEDGE_SERVICE_UNAVAILABLE",
                summary="Knowledge lookup failed safely.",
                latency_ms=1.0,
            )
        ],
        "completed_at": datetime.now(),
        "error_codes": ["KNOWLEDGE_SERVICE_UNAVAILABLE"],
        "missing_fields": [],
        "tool_call_count": 1,
        "total_latency_ms": 1.0,
        "final_response": "Manual review required.",
    }
    row = evaluate_case(case, state)
    assert row["system_error"] is True
    assert row["task_success"] is False
    assert row["primary_failure"] == "SYSTEM_ERROR"
