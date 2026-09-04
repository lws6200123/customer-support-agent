#!/usr/bin/env python3
"""Run a small real DeepSeek + RAGFlow Stage 5 integration smoke suite."""

from __future__ import annotations

import sys
import socket
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import exists, func, select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from customer_support_agent.agent.schemas import AgentRequest  # noqa: E402
from customer_support_agent.agent.workflow import SupportAgentWorkflow  # noqa: E402
from customer_support_agent.core.config import AppSettings, SIMULATION_NOW  # noqa: E402
from customer_support_agent.db.engine import create_sqlite_engine  # noqa: E402
from customer_support_agent.db.models import (  # noqa: E402
    CustomerSupportProfile,
    Order,
    Payment,
    Refund,
)
from customer_support_agent.llm.adapter import DeepSeekChatModel  # noqa: E402


REPORT_PATH = PROJECT_ROOT / "reports" / "stage5_agent_smoke.md"


def _candidate(engine, *, risk: bool = False, minimum_total: float = 0.0):  # type: ignore[no-untyped-def]
    prior_refund = exists(select(Refund.refund_id).where(Refund.customer_id == Order.customer_id))
    statement = (
        select(
            Order.order_id,
            Order.customer_id,
            func.sum(Payment.payment_value).label("payment_total"),
        )
        .join(CustomerSupportProfile, CustomerSupportProfile.customer_id == Order.customer_id)
        .join(Payment, Payment.order_id == Order.order_id)
        .where(
            Order.status == "delivered",
            Order.delivered_at >= SIMULATION_NOW - timedelta(days=7),
            Order.delivered_at <= SIMULATION_NOW,
            Order.source_data_quality_flag == "none",
            CustomerSupportProfile.risk_flag == risk,
            CustomerSupportProfile.account_status == "active",
            CustomerSupportProfile.identity_verified.is_(True),
            ~prior_refund,
        )
        .group_by(Order.order_id)
        .having(func.sum(Payment.payment_value) >= minimum_total)
        .order_by(Order.order_id)
        .limit(1)
    )
    with engine.connect() as connection:
        row = connection.execute(statement).first()
    if row is None:
        raise RuntimeError("No deterministic smoke candidate was found")
    return row


def build_cases(engine) -> list[dict[str, Any]]:  # type: ignore[no-untyped-def]
    normal = _candidate(engine)
    risky = _candidate(engine, risk=True)
    expensive = _candidate(engine, minimum_total=501.0)
    return [
        {
            "case_id": "AS-01",
            "expected_intent": "RETURN_REFUND",
            "expected_decision": "AUTO_RESOLVE",
            "request": AgentRequest(
                user_message=(
                    f"I want a no-reason return for order {normal.order_id}. The item is unused, "
                    f"complete, and in good condition. Requested amount is 20 BRL."
                ),
                customer_id=normal.customer_id,
                order_id=normal.order_id,
            ),
        },
        {
            "case_id": "AS-02",
            "expected_intent": "RETURN_REFUND",
            "expected_decision": "NEED_MORE_INFO",
            "request": AgentRequest(user_message="I want a refund but I do not have my order ID."),
        },
        {
            "case_id": "AS-03",
            "expected_intent": "RETURN_REFUND",
            "expected_decision": "ESCALATE_TO_HUMAN",
            "request": AgentRequest(
                user_message=(
                    f"Please process a no-reason return for order {risky.order_id}. The item is "
                    "unused and complete. Requested amount is 20 BRL."
                ),
                customer_id=risky.customer_id,
                order_id=risky.order_id,
            ),
        },
        {
            "case_id": "AS-04",
            "expected_intent": "DELIVERY",
            "expected_decision": "AUTO_RESOLVE",
            "request": AgentRequest(
                user_message=f"Please explain the delivery status for order {normal.order_id}.",
                customer_id=normal.customer_id,
                order_id=normal.order_id,
            ),
        },
        {
            "case_id": "AS-05",
            "expected_intent": "PRODUCT_AFTER_SALES",
            "expected_decision": "AUTO_RESOLVE",
            "request": AgentRequest(
                user_message=f"Product in order {normal.order_id} appears defective. What evidence is needed?",
                customer_id=normal.customer_id,
                order_id=normal.order_id,
            ),
        },
        {
            "case_id": "AS-06",
            "expected_intent": "ACCOUNT",
            "expected_decision": "AUTO_RESOLVE",
            "request": AgentRequest(
                user_message="I am concerned about account security and want the safe next steps.",
                customer_id=normal.customer_id,
            ),
        },
        {
            "case_id": "AS-07",
            "expected_intent": "INVOICE",
            "expected_decision": "AUTO_RESOLVE",
            "request": AgentRequest(
                user_message=f"What details are needed to request an invoice for order {normal.order_id}?",
                customer_id=normal.customer_id,
                order_id=normal.order_id,
            ),
        },
        {
            "case_id": "AS-08",
            "expected_intent": "OTHER",
            "expected_decision": "AUTO_RESOLVE",
            "request": AgentRequest(user_message="Hello, what kinds of support can you provide?"),
        },
        {
            "case_id": "AS-09",
            "expected_intent": "RETURN_REFUND",
            "expected_decision": "ESCALATE_TO_HUMAN",
            "request": AgentRequest(
                user_message=(
                    f"I request a no-reason return of 501 BRL for order {expensive.order_id}. "
                    "The item is unused, complete, and in good condition."
                ),
                customer_id=expensive.customer_id,
                order_id=expensive.order_id,
            ),
        },
        {
            "case_id": "AS-10",
            "expected_intent": "DELIVERY",
            "expected_decision": "NEED_MORE_INFO",
            "request": AgentRequest(user_message="My package is late, but I cannot find the order ID."),
        },
    ]


def _blocked_report(reasons: list[str]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        "\n".join(
            [
                "# Stage 5 Agent Integration Smoke",
                "",
                "## Status",
                "",
                "**BLOCKED — not executed.**",
                "",
                "The real DeepSeek + RAGFlow integration smoke was not run because an integration precondition failed.",
                "",
                "Blocking preconditions:",
                "",
                *[f"- `{reason}`" for reason in reasons],
                "",
                "No API key value was read into this report. No smoke result or metric has been fabricated.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_report(rows: list[dict[str, Any]]) -> None:
    passed = sum(row["passed"] for row in rows)
    lines = [
        "# Stage 5 Agent Integration Smoke",
        "",
        "## Scope",
        "",
        "This is a limited real DeepSeek + Stage 4 Tools + RAGFlow integration smoke. It is not a final evaluation benchmark and does not execute refunds.",
        "",
        "## Result",
        "",
        f"- Total cases: {len(rows)}",
        f"- Completed cases: {sum(row['completed'] for row in rows)}",
        f"- Expected intent and decision passed: {passed}/{len(rows)}",
        "- Secrets, full prompts, full RAG chunks, customer/order identifiers, and dataset identifiers are omitted",
        "",
        "| Case | Intent | Decision | Tools | Calls | Latency ms | Result |",
        "|---|---|---|---|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['case_id']} | {row['intent']} | {row['decision']} | "
            f"{', '.join(row['tools']) or 'none'} | {row['tool_count']} | "
            f"{row['latency_ms']:.1f} | {'PASS' if row['passed'] else 'FAIL'} |"
        )
    failures = [row for row in rows if not row["passed"]]
    lines.extend(["", "## Failures", ""])
    if failures:
        for row in failures:
            lines.append(
                f"- `{row['case_id']}` expected `{row['expected_intent']}` / "
                f"`{row['expected_decision']}`; observed `{row['intent']}` / `{row['decision']}`; "
                f"error codes: `{row['error_codes']}`."
            )
    else:
        lines.append("No failed cases.")
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "This suite checks a small fixed set of requests against one configured model and knowledge dataset. It does not measure production accuracy, safety, latency SLOs, or final benchmark performance.",
            "",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    settings = AppSettings()
    missing: list[str] = []
    if not settings.deepseek_api_key.get_secret_value().strip():
        missing.append("DEEPSEEK_API_KEY")
    if not settings.deepseek_base_url.strip():
        missing.append("DEEPSEEK_BASE_URL")
    if not settings.deepseek_model.strip():
        missing.append("DEEPSEEK_MODEL")
    if not settings.ragflow_base_url.strip():
        missing.append("RAGFLOW_BASE_URL")
    if not settings.ragflow_api_key.get_secret_value().strip():
        missing.append("RAGFLOW_API_KEY")
    if not settings.ragflow_dataset_id.strip():
        missing.append("RAGFLOW_DATASET_ID")
    if missing:
        _blocked_report(missing)
        print("Stage 5 real integration smoke: BLOCKED (required local configuration missing)")
        print(f"Report: {REPORT_PATH}")
        return 2

    hostname = urlparse(settings.deepseek_base_url).hostname
    try:
        if not hostname:
            raise ValueError("DeepSeek base URL has no hostname")
        socket.getaddrinfo(hostname, None)
    except (OSError, ValueError):
        _blocked_report(["DEEPSEEK_BASE_URL_HOST_UNRESOLVED"])
        print("Stage 5 real integration smoke: BLOCKED (DeepSeek host cannot be resolved)")
        print(f"Report: {REPORT_PATH}")
        return 2

    engine = create_sqlite_engine(settings.database_path)
    model = DeepSeekChatModel(settings)
    try:
        workflow = SupportAgentWorkflow(
            model,
            engine=engine,
            settings=settings,
        )
        rows: list[dict[str, Any]] = []
        for case in build_cases(engine):
            try:
                state = workflow.run(case["request"])
                intent = state.get("intent")
                decision = state.get("decision")
                observed_intent = intent.value if intent else "none"
                observed_decision = decision.value if decision else "none"
                rows.append(
                    {
                        "case_id": case["case_id"],
                        "expected_intent": case["expected_intent"],
                        "expected_decision": case["expected_decision"],
                        "intent": observed_intent,
                        "decision": observed_decision,
                        "tools": [record.tool_name for record in state.get("tool_results", [])],
                        "tool_count": state.get("tool_call_count", 0),
                        "latency_ms": state.get("total_latency_ms", 0.0) or 0.0,
                        "error_codes": state.get("error_codes", []),
                        "completed": bool(state.get("completed_at")),
                        "passed": (
                            observed_intent == case["expected_intent"]
                            and observed_decision == case["expected_decision"]
                            and bool(state.get("completed_at"))
                        ),
                    }
                )
            except Exception:
                rows.append(
                    {
                        "case_id": case["case_id"],
                        "expected_intent": case["expected_intent"],
                        "expected_decision": case["expected_decision"],
                        "intent": "none",
                        "decision": "FAILED",
                        "tools": [],
                        "tool_count": 0,
                        "latency_ms": 0.0,
                        "error_codes": ["SAFE_INTEGRATION_FAILURE"],
                        "completed": False,
                        "passed": False,
                    }
                )
        _write_report(rows)
    finally:
        engine.dispose()
        model.close()
    passed = sum(row["passed"] for row in rows)
    print(f"Stage 5 real integration smoke: {passed}/{len(rows)} passed")
    print(f"Report: {REPORT_PATH}")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
