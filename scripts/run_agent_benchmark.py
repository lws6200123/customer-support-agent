#!/usr/bin/env python3
"""Run the frozen Stage 8A benchmark with real DeepSeek, RAGFlow, LangGraph, and tools."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.audit_agent_benchmark import (  # noqa: E402
    AUDIT_REPORT_PATH,
    BENCHMARK_PATH,
    EVALUATION_DB_PATH,
    audit_benchmark,
    sha256_file,
)
from customer_support_agent.agent.schemas import AgentRequest, AgentRunStatus  # noqa: E402
from customer_support_agent.agent.workflow import SupportAgentWorkflow  # noqa: E402
from customer_support_agent.core.config import AppSettings  # noqa: E402
from customer_support_agent.core.security import sanitize_text  # noqa: E402
from customer_support_agent.db.engine import create_sqlite_engine  # noqa: E402
from customer_support_agent.llm.adapter import DeepSeekChatModel  # noqa: E402


RESULTS_DIR = PROJECT_ROOT / "data" / "evaluation" / "results"
BENCHMARK_REPORT_PATH = PROJECT_ROOT / "reports" / "stage8a_agent_benchmark.md"
FAILURE_REPORT_PATH = PROJECT_ROOT / "reports" / "stage8a_failure_analysis.md"
SYSTEM_ERROR_CODES = {
    "DATABASE_ERROR",
    "KNOWLEDGE_SERVICE_UNAVAILABLE",
    "KNOWLEDGE_CONFIG_MISSING",
    "LLM_CONFIG_MISSING",
    "LLM_UNAVAILABLE",
    "LLM_STRUCTURED_OUTPUT_FAILED",
    "AGENT_STEP_LIMIT_REACHED",
}


def _value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _ratio(numerator: int | float, denominator: int | float) -> float | None:
    return float(numerator) / float(denominator) if denominator else None


def _f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None or precision + recall == 0:
        return None
    return 2 * precision * recall / (precision + recall)


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def classify_failures(row: dict[str, Any]) -> tuple[str | None, list[str]]:
    if row["task_success"]:
        return None, []
    failures: list[str] = []
    errors = set(row["error_codes"])
    if row["system_error"]:
        failures.append("SYSTEM_ERROR")
    if "LLM_STRUCTURED_OUTPUT_FAILED" in errors:
        failures.append("LLM_STRUCTURED_OUTPUT_ERROR")
    if not row["knowledge_retrieval_success"] and "search_knowledge" in row["actual_tool_sequence"]:
        failures.append("KNOWLEDGE_RETRIEVAL_FAILURE")
    if any(not item["ok"] for item in row["tool_results"]):
        failures.append("TOOL_ERROR")
    if not row["intent_correct"]:
        failures.append("INTENT_ERROR")
    if not row["required_tools_satisfied"]:
        failures.append("MISSING_REQUIRED_TOOL")
    if row["unexpected_tools"]:
        failures.extend(["UNNECESSARY_TOOL", "PLANNING_ERROR"])
    if not row["missing_fields_correct"]:
        failures.append("MISSING_INFO_ROUTING_ERROR")
    if not row["decision_correct"]:
        failures.append(
            "MISSING_INFO_ROUTING_ERROR"
            if row["expected_decision"] == "NEED_MORE_INFO"
            else "DECISION_ERROR"
        )
    failures = list(dict.fromkeys(failures))
    if not row["task_success"] and not failures:
        failures.append("UNKNOWN")
    primary_order = [
        "SYSTEM_ERROR",
        "LLM_STRUCTURED_OUTPUT_ERROR",
        "KNOWLEDGE_RETRIEVAL_FAILURE",
        "TOOL_ERROR",
        "INTENT_ERROR",
        "DECISION_ERROR",
        "MISSING_INFO_ROUTING_ERROR",
        "MISSING_REQUIRED_TOOL",
        "UNNECESSARY_TOOL",
        "PLANNING_ERROR",
        "POLICY_AMBIGUITY",
        "UNKNOWN",
    ]
    primary = next((name for name in primary_order if name in failures), None)
    secondary = [name for name in failures if name != primary]
    return primary, secondary


def evaluate_case(case: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    predicted_intent = _value(state.get("intent"))
    predicted_decision = _value(state.get("decision"))
    run_status = _value(state.get("run_status")) or "FAILED"
    tool_records = state.get("tool_results", [])
    tool_results = [
        {
            "tool": record.tool_name,
            "ok": bool(record.ok),
            "error_code": record.error_code,
        }
        for record in tool_records
    ]
    actual_sequence = [item["tool"] for item in tool_results]
    actual_set = set(actual_sequence)
    required = set(case["required_tools"])
    optional = set(case["allowed_optional_tools"])
    forbidden = set(case["forbidden_tools"])
    missing_required = sorted(required - actual_set)
    unexpected = sorted(actual_set - required - optional)
    forbidden_called = sorted(actual_set & forbidden)
    expected_missing = case.get("expected_missing_fields")
    actual_missing = sorted(set(state.get("missing_fields", [])))
    missing_correct = expected_missing is None or actual_missing == sorted(set(expected_missing))
    completed = bool(
        state.get("completed_at")
        and run_status != AgentRunStatus.FAILED.value
        and not state.get("fatal_error")
    )
    errors = sorted(set(str(item) for item in state.get("error_codes", [])))
    system_error = bool(
        run_status == AgentRunStatus.FAILED.value
        or state.get("fatal_error")
        or set(errors) & SYSTEM_ERROR_CODES
    )
    knowledge_records = [item for item in tool_results if item["tool"] == "search_knowledge"]
    knowledge_success: bool | None = None
    if knowledge_records:
        knowledge_success = all(item["ok"] for item in knowledge_records)
    policy_evidence = state.get("policy_evidence", [])
    top_policy_document = policy_evidence[0].document_id if policy_evidence else None
    intent_correct = predicted_intent == case["expected_intent"]
    decision_correct = predicted_decision == case["expected_decision"]
    required_satisfied = not missing_required
    task_success = bool(
        completed
        and not system_error
        and intent_correct
        and decision_correct
        and required_satisfied
        and not unexpected
        and not forbidden_called
        and missing_correct
    )
    response_excerpt = sanitize_text(state.get("final_response"), max_length=300)
    row: dict[str, Any] = {
        "case_id": case["case_id"],
        "risk_class": case["risk_class"],
        "expected_intent": case["expected_intent"],
        "predicted_intent": predicted_intent,
        "expected_decision": case["expected_decision"],
        "predicted_decision": predicted_decision,
        "required_tools": case["required_tools"],
        "allowed_optional_tools": case["allowed_optional_tools"],
        "forbidden_tools": case["forbidden_tools"],
        "actual_tool_sequence": actual_sequence,
        "missing_required_tools": missing_required,
        "unexpected_tools": unexpected,
        "forbidden_tools_called": forbidden_called,
        "intent_correct": intent_correct,
        "decision_correct": decision_correct,
        "required_tools_satisfied": required_satisfied,
        "forbidden_tool_called": bool(forbidden_called),
        "tool_exact_match": actual_set == required,
        "expected_missing_fields": expected_missing,
        "actual_missing_fields": actual_missing,
        "missing_fields_correct": missing_correct,
        "task_success": task_success,
        "run_status": run_status,
        "latency_ms": round(float(state.get("total_latency_ms") or 0.0), 3),
        "tool_call_count": int(state.get("tool_call_count", len(actual_sequence))),
        "error_codes": errors,
        "system_error": system_error,
        "tool_results": tool_results,
        "knowledge_retrieval_success": knowledge_success,
        "top_policy_document": top_policy_document,
        "response_excerpt": response_excerpt,
    }
    primary, secondary = classify_failures(row)
    row["primary_failure"] = primary
    row["secondary_failures"] = secondary
    row["safety_risk"] = case["risk_class"] == "escalation-critical" and not task_success
    row["worth_fixing"] = bool(
        primary
        and primary
        not in {"INTENT_ERROR", "POLICY_AMBIGUITY"}
    )
    return row


def failed_case(case: dict[str, Any], exc: Exception) -> dict[str, Any]:
    del exc
    row = {
        "case_id": case["case_id"],
        "risk_class": case["risk_class"],
        "expected_intent": case["expected_intent"],
        "predicted_intent": None,
        "expected_decision": case["expected_decision"],
        "predicted_decision": None,
        "required_tools": case["required_tools"],
        "allowed_optional_tools": case["allowed_optional_tools"],
        "forbidden_tools": case["forbidden_tools"],
        "actual_tool_sequence": [],
        "missing_required_tools": case["required_tools"],
        "unexpected_tools": [],
        "forbidden_tools_called": [],
        "intent_correct": False,
        "decision_correct": False,
        "required_tools_satisfied": not case["required_tools"],
        "forbidden_tool_called": False,
        "tool_exact_match": not case["required_tools"],
        "expected_missing_fields": case.get("expected_missing_fields"),
        "actual_missing_fields": [],
        "missing_fields_correct": False,
        "task_success": False,
        "run_status": "FAILED",
        "latency_ms": 0.0,
        "tool_call_count": 0,
        "error_codes": ["SAFE_BENCHMARK_CASE_FAILURE"],
        "system_error": True,
        "tool_results": [],
        "knowledge_retrieval_success": None,
        "top_policy_document": None,
        "response_excerpt": None,
        "primary_failure": "SYSTEM_ERROR",
        "secondary_failures": ["MISSING_REQUIRED_TOOL"] if case["required_tools"] else [],
        "safety_risk": case["risk_class"] == "escalation-critical",
        "worth_fixing": True,
    }
    return row


def compute_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    intent_correct = sum(row["intent_correct"] for row in rows)
    decision_correct = sum(row["decision_correct"] for row in rows)
    task_successes = sum(row["task_success"] for row in rows)
    per_intent: dict[str, Any] = {}
    for intent in sorted({row["expected_intent"] for row in rows}):
        selected = [row for row in rows if row["expected_intent"] == intent]
        per_intent[intent] = {
            "total": len(selected),
            "correct": sum(row["intent_correct"] for row in selected),
            "accuracy": _ratio(sum(row["intent_correct"] for row in selected), len(selected)),
        }
    per_decision: dict[str, Any] = {}
    for decision in ("AUTO_RESOLVE", "NEED_MORE_INFO", "ESCALATE_TO_HUMAN"):
        selected = [row for row in rows if row["expected_decision"] == decision]
        per_decision[decision] = {
            "total": len(selected),
            "correct": sum(row["decision_correct"] for row in selected),
            "accuracy": _ratio(sum(row["decision_correct"] for row in selected), len(selected)),
        }
    escalation_tp = sum(
        row["expected_decision"] == "ESCALATE_TO_HUMAN"
        and row["predicted_decision"] == "ESCALATE_TO_HUMAN"
        for row in rows
    )
    escalation_fp = sum(
        row["expected_decision"] != "ESCALATE_TO_HUMAN"
        and row["predicted_decision"] == "ESCALATE_TO_HUMAN"
        for row in rows
    )
    escalation_fn = sum(
        row["expected_decision"] == "ESCALATE_TO_HUMAN"
        and row["predicted_decision"] != "ESCALATE_TO_HUMAN"
        for row in rows
    )
    escalation_precision = _ratio(escalation_tp, escalation_tp + escalation_fp)
    escalation_recall = _ratio(escalation_tp, escalation_tp + escalation_fn)

    tool_tp = tool_fp = tool_fn = 0
    for row in rows:
        actual = set(row["actual_tool_sequence"])
        required = set(row["required_tools"])
        optional = set(row["allowed_optional_tools"])
        tool_tp += len(actual & required)
        tool_fn += len(required - actual)
        tool_fp += len(actual - required - optional)
    tool_precision = _ratio(tool_tp, tool_tp + tool_fp)
    tool_recall = _ratio(tool_tp, tool_tp + tool_fn)
    latencies = [float(row["latency_ms"]) for row in rows if row["latency_ms"] >= 0]
    failure_counts = Counter(
        row["primary_failure"] for row in rows if row["primary_failure"] is not None
    )
    critical = [row for row in rows if row["risk_class"] == "escalation-critical"]
    missed_escalations = [
        row["case_id"]
        for row in critical
        if row["predicted_decision"] != "ESCALATE_TO_HUMAN"
    ]
    return {
        "case_count": total,
        "intent_accuracy": _ratio(intent_correct, total),
        "intent_correct": intent_correct,
        "per_intent": per_intent,
        "decision_accuracy": _ratio(decision_correct, total),
        "decision_correct": decision_correct,
        "per_decision": per_decision,
        "escalation": {
            "true_positive": escalation_tp,
            "false_positive": escalation_fp,
            "false_negative": escalation_fn,
            "precision": escalation_precision,
            "recall": escalation_recall,
            "f1": _f1(escalation_precision, escalation_recall),
        },
        "tools": {
            "true_positive": tool_tp,
            "false_positive": tool_fp,
            "false_negative": tool_fn,
            "precision": tool_precision,
            "recall": tool_recall,
            "f1": _f1(tool_precision, tool_recall),
            "exact_set_accuracy": _ratio(sum(row["tool_exact_match"] for row in rows), total),
        },
        "task_success_rate": _ratio(task_successes, total),
        "task_success_count": task_successes,
        "average_tool_calls": statistics.fmean(row["tool_call_count"] for row in rows) if rows else None,
        "latency_ms": {
            "mean": statistics.fmean(latencies) if latencies else None,
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
            "min": min(latencies) if latencies else None,
            "max": max(latencies) if latencies else None,
        },
        "failure_count": total - task_successes,
        "system_error_rate": _ratio(sum(row["system_error"] for row in rows), total),
        "system_error_count": sum(row["system_error"] for row in rows),
        "failure_taxonomy": dict(sorted(failure_counts.items())),
        "escalation_critical": {
            "total": len(critical),
            "correctly_escalated": len(critical) - len(missed_escalations),
            "missed_count": len(missed_escalations),
            "missed_cases": missed_escalations,
        },
    }


def _fmt_ratio(value: float | None) -> str:
    return "N/A" if value is None else f"{value * 100:.2f}%"


def _fmt_number(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.1f}"


def write_case_results(rows: list[dict[str, Any]], run_key: str) -> tuple[Path, Path]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RESULTS_DIR / f"{run_key}_cases.json"
    csv_path = RESULTS_DIR / f"{run_key}_cases.csv"
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    scalar_fields = [
        "case_id", "risk_class", "expected_intent", "predicted_intent",
        "expected_decision", "predicted_decision", "intent_correct", "decision_correct",
        "required_tools_satisfied", "forbidden_tool_called", "tool_exact_match",
        "missing_fields_correct", "task_success", "run_status", "latency_ms",
        "tool_call_count", "system_error", "knowledge_retrieval_success",
        "top_policy_document", "primary_failure", "safety_risk", "worth_fixing",
    ]
    list_fields = [
        "required_tools", "allowed_optional_tools", "forbidden_tools", "actual_tool_sequence",
        "missing_required_tools", "unexpected_tools", "forbidden_tools_called",
        "expected_missing_fields", "actual_missing_fields", "error_codes", "secondary_failures",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=scalar_fields + list_fields,
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            output = {field: row.get(field) for field in scalar_fields}
            output.update(
                {
                    field: "|".join(str(value) for value in (row.get(field) or []))
                    for field in list_fields
                }
            )
            writer.writerow(output)
    return json_path, csv_path


def write_reports(
    rows: list[dict[str, Any]], metrics: dict[str, Any], metadata: dict[str, Any]
) -> None:
    lines = [
        "# Stage 8A Agent Benchmark",
        "",
        "## Benchmark Configuration",
        "",
        f"- Official run: `{metadata['run_id']}`",
        f"- Cases: {metrics['case_count']}",
        f"- Benchmark SHA256: `{metadata['benchmark_sha256']}`",
        f"- Git commit: `{metadata['git_commit']}`",
        f"- DeepSeek model: `{metadata['deepseek_model']}`",
        f"- Business rules version: `{metadata['business_rules_version']}`",
        f"- Simulation clock: `{metadata['simulation_clock']}`",
        "- Execution: sequential, real DeepSeek + RAGFlow + LangGraph + Stage 4 tools",
        "- Runtime: isolated disposable evaluation SQLite database",
        "",
        "## Dataset Distribution",
        "",
        f"- Intent: `{metadata['intent_distribution']}`",
        f"- Decision: `{metadata['decision_distribution']}`",
        f"- Escalation-critical: {metrics['escalation_critical']['total']}",
        "",
        "## Overall Metrics",
        "",
        f"- Intent Accuracy: {_fmt_ratio(metrics['intent_accuracy'])} ({metrics['intent_correct']}/{metrics['case_count']})",
        f"- Decision Accuracy: {_fmt_ratio(metrics['decision_accuracy'])} ({metrics['decision_correct']}/{metrics['case_count']})",
        f"- Task Success Rate: {_fmt_ratio(metrics['task_success_rate'])} ({metrics['task_success_count']}/{metrics['case_count']})",
        f"- Exact Tool Set Accuracy: {_fmt_ratio(metrics['tools']['exact_set_accuracy'])}",
        f"- Failure Count: {metrics['failure_count']}",
        f"- System Error Rate: {_fmt_ratio(metrics['system_error_rate'])} ({metrics['system_error_count']}/{metrics['case_count']})",
        "",
        "## Per-Intent Accuracy",
        "",
        "| Intent | Correct | Total | Accuracy |",
        "|---|---:|---:|---:|",
    ]
    for intent, row in metrics["per_intent"].items():
        lines.append(f"| {intent} | {row['correct']} | {row['total']} | {_fmt_ratio(row['accuracy'])} |")
    lines.extend(
        [
            "",
            "## Decision Metrics",
            "",
            "| Decision | Correct | Total | Accuracy |",
            "|---|---:|---:|---:|",
        ]
    )
    for decision, row in metrics["per_decision"].items():
        lines.append(f"| {decision} | {row['correct']} | {row['total']} | {_fmt_ratio(row['accuracy'])} |")
    escalation = metrics["escalation"]
    tools = metrics["tools"]
    latency = metrics["latency_ms"]
    lines.extend(
        [
            "",
            "## Safety Metrics",
            "",
            f"- Escalation Precision: {_fmt_ratio(escalation['precision'])}",
            f"- Escalation Recall: {_fmt_ratio(escalation['recall'])}",
            f"- Escalation F1: {_fmt_ratio(escalation['f1'])}",
            f"- Correctly escalated critical cases: {metrics['escalation_critical']['correctly_escalated']}/{metrics['escalation_critical']['total']}",
            f"- Missed critical escalations: {metrics['escalation_critical']['missed_count']}",
            "",
            "## Tool Metrics",
            "",
            f"- Tool Selection Precision: {_fmt_ratio(tools['precision'])}",
            f"- Tool Selection Recall: {_fmt_ratio(tools['recall'])}",
            f"- Tool Selection F1: {_fmt_ratio(tools['f1'])}",
            f"- Exact Tool Set Accuracy: {_fmt_ratio(tools['exact_set_accuracy'])}",
            f"- Average Tool Calls: {_fmt_number(metrics['average_tool_calls'])}",
            "",
            "## Latency",
            "",
            f"- Mean: {_fmt_number(latency['mean'])} ms",
            f"- P50: {_fmt_number(latency['p50'])} ms",
            f"- P95: {_fmt_number(latency['p95'])} ms",
            f"- Min: {_fmt_number(latency['min'])} ms",
            f"- Max: {_fmt_number(latency['max'])} ms",
            "",
            "## Retrieval Observation",
            "",
            f"- Knowledge calls observed: {sum('search_knowledge' in row['actual_tool_sequence'] for row in rows)}",
            f"- Successful knowledge calls: {sum(row['knowledge_retrieval_success'] is True for row in rows)}",
            f"- Failed knowledge calls: {sum(row['knowledge_retrieval_success'] is False for row in rows)}",
            "",
            "## Failure Summary",
            "",
            f"- Primary taxonomy counts: `{metrics['failure_taxonomy']}`",
            f"- Missed escalation cases: `{metrics['escalation_critical']['missed_cases']}`",
            "",
            "## Known Limitations",
            "",
            "This is a controlled 60-case portfolio benchmark against one configured model and knowledge dataset. It is not production traffic, a production SLA, or an industry benchmark. Latency includes external service conditions during this single sequential run. AUTO_RESOLVE is only a routing candidate and does not execute a refund.",
            "",
        ]
    )
    BENCHMARK_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")

    failed = [row for row in rows if not row["task_success"]]
    taxonomy = Counter(row["primary_failure"] or "UNKNOWN" for row in failed)
    failure_lines = [
        "# Stage 8A Failure Analysis",
        "",
        f"- Official run: `{metadata['run_id']}`",
        f"- Total failures: {len(failed)}/{len(rows)}",
        f"- Primary failure taxonomy: `{dict(sorted(taxonomy.items()))}`",
        "",
        "## Failed Cases",
        "",
    ]
    if not failed:
        failure_lines.append("No failed cases.")
    for row in failed:
        reason = ", ".join(
            filter(
                None,
                [
                    f"intent {row['expected_intent']} → {row['predicted_intent']}" if not row["intent_correct"] else "",
                    f"decision {row['expected_decision']} → {row['predicted_decision']}" if not row["decision_correct"] else "",
                    f"missing tools {row['missing_required_tools']}" if row["missing_required_tools"] else "",
                    f"unexpected tools {row['unexpected_tools']}" if row["unexpected_tools"] else "",
                    f"missing fields {row['expected_missing_fields']} → {row['actual_missing_fields']}" if not row["missing_fields_correct"] else "",
                    f"errors {row['error_codes']}" if row["error_codes"] else "",
                ],
            )
        ) or "Task-success contract was not satisfied."
        failure_lines.extend(
            [
                f"### {row['case_id']}",
                "",
                f"- Expected: `{row['expected_intent']}` / `{row['expected_decision']}`",
                f"- Actual: `{row['predicted_intent']}` / `{row['predicted_decision']}`",
                f"- Tool sequence: `{row['actual_tool_sequence']}`",
                f"- Primary / secondary: `{row['primary_failure']}` / `{row['secondary_failures']}`",
                f"- Reason: {reason}",
                f"- Safety risk: {'yes' if row['safety_risk'] else 'no'}",
                f"- Worth fixing: {'yes — only with a generalizable implementation fix' if row['worth_fixing'] else 'review as a model/generalization limitation; no case-specific fix'}",
                "",
            ]
        )
    missed = [
        row
        for row in rows
        if row["risk_class"] == "escalation-critical"
        and row["predicted_decision"] != "ESCALATE_TO_HUMAN"
    ]
    failure_lines.extend(["## Missed Escalation-Critical Cases", ""])
    failure_lines.extend(
        [
            f"- `{row['case_id']}` expected escalation but predicted `{row['predicted_decision']}`."
            for row in missed
        ]
        or ["No missed escalation-critical cases."]
    )
    failure_lines.extend(
        [
            "",
            "## Interpretation Boundary",
            "",
            "Failures are classified by observable intent, decision, tools, missing fields, retrieval status, and safe error codes. They are not reduced to an unsupported claim that the LLM was simply wrong.",
            "",
        ]
    )
    FAILURE_REPORT_PATH.write_text("\n".join(failure_lines), encoding="utf-8")


def run_benchmark(run_id: str) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    document, errors, audit_summary = audit_benchmark()
    if errors:
        raise RuntimeError(f"Benchmark audit failed; see {AUDIT_REPORT_PATH}")
    initial_hash = audit_summary["sha256"]
    settings = AppSettings(database_path=EVALUATION_DB_PATH)
    if not settings.deepseek_configured:
        raise RuntimeError("DeepSeek configuration is missing")
    if not settings.ragflow_configured:
        raise RuntimeError("RAGFlow configuration is missing")
    rules = yaml.safe_load((PROJECT_ROOT / "knowledge" / "business_rules.yaml").read_text(encoding="utf-8"))
    git_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, text=True).strip()
    started_at = datetime.now(timezone.utc)
    engine = create_sqlite_engine(EVALUATION_DB_PATH)
    model = DeepSeekChatModel(settings)
    workflow = SupportAgentWorkflow(model, engine=engine, settings=settings)
    rows: list[dict[str, Any]] = []
    try:
        for index, case in enumerate(document["cases"], start=1):
            try:
                state = workflow.run(
                    AgentRequest(
                        user_message=case["message"],
                        customer_id=case.get("customer_id"),
                        order_id=case.get("order_id"),
                    )
                )
                row = evaluate_case(case, state)
            except Exception as exc:
                row = failed_case(case, exc)
            rows.append(row)
            print(
                f"[{index:02d}/{len(document['cases'])}] {case['case_id']} "
                f"intent={row['predicted_intent']} decision={row['predicted_decision']} "
                f"task={'PASS' if row['task_success'] else 'FAIL'} latency_ms={row['latency_ms']:.1f}",
                flush=True,
            )
    finally:
        engine.dispose()
        model.close()
    final_hash = sha256_file(BENCHMARK_PATH)
    if final_hash != initial_hash:
        raise RuntimeError("Benchmark changed during the official run; results are not valid")
    metrics = compute_metrics(rows)
    metadata = {
        "run_id": run_id,
        "official": True,
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "benchmark_path": str(BENCHMARK_PATH.relative_to(PROJECT_ROOT)),
        "benchmark_sha256": initial_hash,
        "git_commit": git_commit,
        "deepseek_model": settings.deepseek_model,
        "ragflow_config": {
            "configured": True,
            "top_n": settings.ragflow_top_n,
            "similarity_threshold": settings.ragflow_similarity_threshold,
            "vector_similarity_weight": settings.ragflow_vector_similarity_weight,
            "reranker_configured": bool(settings.ragflow_rerank_id),
        },
        "business_rules_version": rules.get("specification_version"),
        "simulation_clock": settings.simulation_now.isoformat(),
        "execution_mode": "sequential",
        "intent_distribution": audit_summary["intent_distribution"],
        "decision_distribution": audit_summary["decision_distribution"],
    }
    run_key = run_id.lower()
    json_path, csv_path = write_case_results(rows, run_key)
    (RESULTS_DIR / f"{run_key}_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RESULTS_DIR / f"{run_key}_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_reports(rows, metrics, metadata)
    print(f"Case JSON: {json_path}")
    print(f"Case CSV: {csv_path}")
    print(f"Task success: {metrics['task_success_count']}/{metrics['case_count']}")
    print(f"Benchmark report: {BENCHMARK_REPORT_PATH}")
    print(f"Failure report: {FAILURE_REPORT_PATH}")
    return rows, metrics, metadata


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="OFFICIAL_RUN_1")
    args = parser.parse_args()
    try:
        run_benchmark(args.run_id)
    except Exception as exc:
        print(f"Stage 8A benchmark blocked safely: {type(exc).__name__}: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
