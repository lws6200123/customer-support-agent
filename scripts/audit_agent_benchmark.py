#!/usr/bin/env python3
"""Audit and freeze the Stage 8A benchmark against deterministic project facts."""

from __future__ import annotations

import hashlib
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import insert, select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from customer_support_agent.agent.schemas import Intent, SubIntent  # noqa: E402
from customer_support_agent.core.config import PROCESSED_DATA_DIR, SIMULATION_NOW  # noqa: E402
from customer_support_agent.core.schemas import (  # noqa: E402
    Decision,
    RefundEvaluationInput,
)
from customer_support_agent.db.engine import create_sqlite_engine  # noqa: E402
from customer_support_agent.db.loader import initialize_database  # noqa: E402
from customer_support_agent.db.models import Customer, Order, Refund  # noqa: E402
from customer_support_agent.services.refund_service import RefundDecisionService  # noqa: E402
from customer_support_agent.services.rules import load_intent_taxonomy  # noqa: E402


BENCHMARK_PATH = PROJECT_ROOT / "data" / "evaluation" / "agent_benchmark.yaml"
EVALUATION_DB_PATH = PROJECT_ROOT / "data" / "evaluation" / "customer_support_eval.db"
AUDIT_REPORT_PATH = PROJECT_ROOT / "reports" / "stage8a_benchmark_audit.md"
EXPECTED_CASE_COUNT = 60
VALID_RISK_CLASSES = {"normal", "escalation-critical", "information-missing"}
VALID_TOOLS = {
    "lookup_customer",
    "lookup_order",
    "list_customer_orders",
    "search_knowledge",
    "evaluate_refund",
}
SECRET_PATTERN = re.compile(
    r"(?i)(?:api[_-]?key|access[_-]?token|secret)\s*[:=]\s*[^\s\"']+|"
    r"(?:ghp_|github_pat_|sk-)[A-Za-z0-9_-]{16,}|BEGIN [A-Z ]*PRIVATE KEY"
)


def load_benchmark(path: Path = BENCHMARK_PATH) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Benchmark root must be a mapping")
    return value


def sha256_file(path: Path = BENCHMARK_PATH) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_evaluation_database(
    document: dict[str, Any], database_path: Path = EVALUATION_DB_PATH
) -> None:
    """Rebuild an isolated DB from processed facts and add declared evaluation fixtures."""
    initialize_database(PROCESSED_DATA_DIR, database_path)
    engine = create_sqlite_engine(database_path)
    try:
        with engine.begin() as connection:
            for fixture in document.get("evaluation_fixtures", []):
                customer_id = fixture["customer_id"]
                order_id = fixture["order_id"]
                for refund in fixture.get("approved_refunds", []):
                    requested_at = datetime.fromisoformat(refund["requested_at"])
                    connection.execute(
                        insert(Refund).values(
                            refund_id=refund["refund_id"],
                            order_id=order_id,
                            customer_id=customer_id,
                            amount=float(refund["amount"]),
                            reason="evaluation_frequency_fixture",
                            status="approved",
                            requested_at=requested_at,
                            resolved_at=requested_at,
                            data_origin="synthetic_evaluation_fixture",
                        )
                    )
    finally:
        engine.dispose()


def _exists(connection, model: Any, field: Any, value: str) -> bool:  # type: ignore[no-untyped-def]
    return connection.scalar(select(model).where(field == value).limit(1)) is not None


def validate_benchmark(
    document: dict[str, Any],
    database_path: Path = EVALUATION_DB_PATH,
    expected_case_count: int = EXPECTED_CASE_COUNT,
) -> list[str]:
    errors: list[str] = []
    cases = document.get("cases")
    if not isinstance(cases, list):
        return ["cases must be a list"]
    if document.get("case_count") != expected_case_count or len(cases) != expected_case_count:
        errors.append(
            f"case count must be {expected_case_count}; declared={document.get('case_count')}, actual={len(cases)}"
        )
    case_ids = [case.get("case_id") for case in cases if isinstance(case, dict)]
    if len(case_ids) != len(set(case_ids)):
        errors.append("case_id values must be unique")
    if any(not isinstance(case_id, str) or not case_id for case_id in case_ids):
        errors.append("every case_id must be a non-empty string")

    taxonomy = load_intent_taxonomy()
    valid_intents = {item.value for item in Intent}
    valid_sub_intents = {item.value for item in SubIntent}
    valid_decisions = {item.value for item in Decision}
    engine = create_sqlite_engine(database_path)
    refund_service = RefundDecisionService(engine, SIMULATION_NOW)
    try:
        with engine.connect() as connection:
            for index, case in enumerate(cases, start=1):
                if not isinstance(case, dict):
                    errors.append(f"case #{index} must be a mapping")
                    continue
                case_id = str(case.get("case_id") or f"case-{index}")
                required_fields = {
                    "case_id", "intent", "message", "expected_intent", "expected_decision",
                    "required_tools", "allowed_optional_tools", "forbidden_tools", "risk_class", "notes",
                }
                missing_keys = sorted(required_fields - set(case))
                if missing_keys:
                    errors.append(f"{case_id}: missing keys {missing_keys}")
                intent = case.get("intent")
                expected_intent = case.get("expected_intent")
                sub_intent = case.get("sub_intent")
                expected_decision = case.get("expected_decision")
                if intent not in valid_intents or expected_intent not in valid_intents:
                    errors.append(f"{case_id}: invalid intent enum")
                if intent != expected_intent:
                    errors.append(f"{case_id}: intent and expected_intent must agree")
                if sub_intent not in valid_sub_intents or sub_intent not in taxonomy.get(str(intent), []):
                    errors.append(f"{case_id}: sub_intent is outside the canonical taxonomy")
                if expected_decision not in valid_decisions:
                    errors.append(f"{case_id}: invalid expected_decision")
                risk_class = case.get("risk_class")
                if risk_class not in VALID_RISK_CLASSES:
                    errors.append(f"{case_id}: invalid risk_class")
                if risk_class == "escalation-critical" and expected_decision != "ESCALATE_TO_HUMAN":
                    errors.append(f"{case_id}: escalation-critical must expect escalation")
                if risk_class == "information-missing" and expected_decision != "NEED_MORE_INFO":
                    errors.append(f"{case_id}: information-missing must expect NEED_MORE_INFO")
                if not isinstance(case.get("message"), str) or not case["message"].strip():
                    errors.append(f"{case_id}: message must be non-empty")

                tool_sets: list[set[str]] = []
                for field in ("required_tools", "allowed_optional_tools", "forbidden_tools"):
                    values = case.get(field)
                    if not isinstance(values, list) or len(values) != len(set(values)):
                        errors.append(f"{case_id}: {field} must be a unique list")
                        tool_sets.append(set())
                        continue
                    unknown = set(values) - VALID_TOOLS
                    if unknown:
                        errors.append(f"{case_id}: unknown tools in {field}: {sorted(unknown)}")
                    tool_sets.append(set(values))
                if any(tool_sets[left] & tool_sets[right] for left, right in ((0, 1), (0, 2), (1, 2))):
                    errors.append(f"{case_id}: required/optional/forbidden tools overlap")
                if intent != "RETURN_REFUND" and "evaluate_refund" not in tool_sets[2]:
                    errors.append(f"{case_id}: non-refund case must forbid evaluate_refund")

                customer_id = case.get("customer_id")
                order_id = case.get("order_id")
                expectations = case.get("identifier_expectation") or {}
                customer_exists = bool(
                    customer_id and _exists(connection, Customer, Customer.customer_id, customer_id)
                )
                order_exists = bool(order_id and _exists(connection, Order, Order.order_id, order_id))
                if customer_id:
                    expected = expectations.get("customer_id", "must_exist")
                    if expected == "must_exist" and not customer_exists:
                        errors.append(f"{case_id}: customer_id does not exist")
                    if expected == "must_not_exist" and customer_exists:
                        errors.append(f"{case_id}: customer_id unexpectedly exists")
                if order_id:
                    expected = expectations.get("order_id", "must_exist")
                    if expected == "must_exist" and not order_exists:
                        errors.append(f"{case_id}: order_id does not exist")
                    if expected == "must_not_exist" and order_exists:
                        errors.append(f"{case_id}: order_id unexpectedly exists")
                if customer_exists and order_exists:
                    actual_customer = connection.scalar(
                        select(Order.customer_id).where(Order.order_id == order_id)
                    )
                    if actual_customer != customer_id:
                        errors.append(f"{case_id}: order/customer identifiers do not match")

                if intent == "RETURN_REFUND":
                    refund_input = case.get("refund_input")
                    if not isinstance(refund_input, dict):
                        errors.append(f"{case_id}: refund_input is required")
                        continue
                    request = RefundEvaluationInput.model_validate(
                        {
                            "order_id": order_id,
                            "issue_description": case["message"],
                            **refund_input,
                        }
                    )
                    result = refund_service.evaluate(request)
                    if result.decision.value != expected_decision:
                        errors.append(
                            f"{case_id}: rule engine returned {result.decision.value}, expected {expected_decision}"
                        )
                    expected_missing = sorted(case.get("expected_missing_fields") or [])
                    if sorted(result.missing_fields) != expected_missing:
                        errors.append(
                            f"{case_id}: refund missing fields {sorted(result.missing_fields)} != {expected_missing}"
                        )
    except Exception as exc:
        errors.append(f"deterministic audit failed safely: {type(exc).__name__}: {exc}")
    finally:
        engine.dispose()

    serialized = yaml.safe_dump(document, allow_unicode=True, sort_keys=False)
    if SECRET_PATTERN.search(serialized):
        errors.append("benchmark contains a credential-shaped value")
    return errors


def build_audit_summary(document: dict[str, Any], digest: str) -> dict[str, Any]:
    cases = document["cases"]
    return {
        "count": len(cases),
        "intent_distribution": dict(sorted(Counter(case["expected_intent"] for case in cases).items())),
        "decision_distribution": dict(sorted(Counter(case["expected_decision"] for case in cases).items())),
        "escalation_critical": sum(case["risk_class"] == "escalation-critical" for case in cases),
        "information_missing": sum(case["risk_class"] == "information-missing" for case in cases),
        "sha256": digest,
    }


def write_audit_report(summary: dict[str, Any], errors: list[str], path: Path = AUDIT_REPORT_PATH) -> None:
    status = "PASS" if not errors else "FAIL"
    lines = [
        "# Stage 8A Benchmark Audit",
        "",
        f"**Status: {status}**",
        "",
        f"- Cases: {summary['count']}",
        f"- Intent distribution: `{summary['intent_distribution']}`",
        f"- Decision distribution: `{summary['decision_distribution']}`",
        f"- Escalation-critical cases: {summary['escalation_critical']}",
        f"- Information-missing cases: {summary['information_missing']}",
        f"- Benchmark SHA256: `{summary['sha256']}`",
        "- Evaluation DB: rebuilt from processed data and isolated from the Demo runtime",
        "- Refund decisions: recomputed with `RefundDecisionService`",
        "- Identifier, taxonomy, tool-set, enum, conflict, and credential checks: completed",
        "",
        "## Ground Truth Sources",
        "",
        "1. Stage 2 SQLite facts and scenario labels.",
        "2. Canonical `knowledge/business_rules.yaml` and `knowledge/decision_examples.yaml`.",
        "3. Deterministic `RefundDecisionService` for every refund case.",
        "4. Human-reviewed intent, tool, missing-information, legal, safety, and routing expectations.",
        "5. An explicitly declared evaluation-only synthetic refund-frequency fixture.",
        "",
        "## Errors",
        "",
    ]
    lines.extend([f"- {error}" for error in errors] or ["No audit errors."])
    lines.extend(
        [
            "",
            "## Statistical Boundary",
            "",
            "This is a 60-case controlled portfolio benchmark, not production traffic, a production SLA, or an industry benchmark.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def audit_benchmark(
    benchmark_path: Path = BENCHMARK_PATH,
    database_path: Path = EVALUATION_DB_PATH,
    report_path: Path = AUDIT_REPORT_PATH,
) -> tuple[dict[str, Any], list[str], dict[str, Any]]:
    document = load_benchmark(benchmark_path)
    prepare_evaluation_database(document, database_path)
    errors = validate_benchmark(document, database_path)
    summary = build_audit_summary(document, sha256_file(benchmark_path))
    write_audit_report(summary, errors, report_path)
    return document, errors, summary


def main() -> int:
    _, errors, summary = audit_benchmark()
    print(f"Stage 8A benchmark audit: {'PASS' if not errors else 'FAIL'}")
    print(f"Cases: {summary['count']}")
    print(f"SHA256: {summary['sha256']}")
    print(f"Report: {AUDIT_REPORT_PATH}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
