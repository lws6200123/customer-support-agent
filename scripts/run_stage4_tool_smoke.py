#!/usr/bin/env python3
"""Run Stage 4 business-tool smoke checks against a disposable SQLite copy."""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import exists, func, select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from customer_support_agent.core.config import AppSettings, PROCESSED_DATA_DIR, SIMULATION_NOW  # noqa: E402
from customer_support_agent.db.engine import create_sqlite_engine  # noqa: E402
from customer_support_agent.db.loader import initialize_database  # noqa: E402
from customer_support_agent.db.models import (  # noqa: E402
    Customer,
    CustomerSupportProfile,
    Order,
    Payment,
    Refund,
)
from customer_support_agent.tools import create_business_tools, tools_by_name  # noqa: E402


REPORT_PATH = PROJECT_ROOT / "reports" / "stage4_tool_smoke.md"


def _decode(value: Any) -> dict[str, Any]:
    return json.loads(value) if isinstance(value, str) else value


def _labelled_order(engine, label: str) -> str:
    with engine.connect() as connection:
        value = connection.scalar(
            select(Order.order_id)
            .where(Order.scenario_labels.contains(label))
            .order_by(Order.order_id)
            .limit(1)
        )
    if value is None:
        raise RuntimeError(f"No order found for scenario {label}")
    return str(value)


def _refund_candidate(
    engine,
    *,
    risk: bool = False,
    minimum_total: float = 0.0,
    anomaly: bool = False,
):  # type: ignore[no-untyped-def]
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
            CustomerSupportProfile.risk_flag == risk,
            CustomerSupportProfile.account_status == "active",
            CustomerSupportProfile.identity_verified.is_(True),
            (Order.source_data_quality_flag != "none")
            if anomaly
            else (Order.source_data_quality_flag == "none"),
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
        raise RuntimeError("No deterministic refund smoke candidate found")
    return row


def _refund_payload(candidate, amount: float | None = None) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    return {
        "order_id": candidate.order_id,
        "reason_code": "NO_REASON",
        "requested_amount": amount or min(float(candidate.payment_total), 50.0),
        "issue_description": "Customer requests a return within the policy window.",
        "product_condition_ok": True,
    }


def _record(
    rows: list[dict[str, str]],
    case_id: str,
    name: str,
    passed: bool,
    evidence: str,
) -> None:
    rows.append(
        {
            "case_id": case_id,
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "evidence": evidence.replace("|", "/").replace("\n", " "),
        }
    )


def run_smoke(engine, settings: AppSettings) -> list[dict[str, str]]:  # type: ignore[no-untyped-def]
    tools = tools_by_name(create_business_tools(engine=engine, settings=settings))
    rows: list[dict[str, str]] = []

    with engine.connect() as connection:
        customer_id = str(connection.scalar(select(Customer.customer_id).order_by(Customer.customer_id).limit(1)))
        normal_order = str(
            connection.scalar(
                select(Order.order_id)
                .where(Order.source_data_quality_flag == "none")
                .order_by(Order.order_id)
                .limit(1)
            )
        )

    result = _decode(tools["lookup_customer"].invoke({"customer_id": customer_id}))
    _record(rows, "TS-01", "valid customer", result["ok"], "customer context returned")
    result = _decode(tools["lookup_customer"].invoke({"customer_id": "CUST-NOT-FOUND"}))
    _record(
        rows,
        "TS-02",
        "missing customer",
        not result["ok"] and result["error_code"] == "CUSTOMER_NOT_FOUND",
        f"error_code={result['error_code']}",
    )

    result = _decode(tools["lookup_order"].invoke({"order_id": normal_order}))
    _record(rows, "TS-03", "normal order", result["ok"], "complete order context returned")
    for case_id, name, label, key in (
        ("TS-04", "multi-item order", "multi_item", "items"),
        ("TS-05", "multi-payment order", "multi_payment", "payments"),
        ("TS-06", "delivered-late order", "delivered_late", "items"),
    ):
        order_id = _labelled_order(engine, label)
        result = _decode(tools["lookup_order"].invoke({"order_id": order_id}))
        size = len(result.get("data", {}).get(key, [])) if result["ok"] else 0
        expected_size = 2 if label in {"multi_item", "multi_payment"} else 1
        passed = result["ok"] and size >= expected_size
        if label == "delivered_late" and result["ok"]:
            data = result["data"]
            passed = data["delivered_at"] > data["estimated_delivery_at"]
        _record(rows, case_id, name, passed, f"order={order_id}; {key}_rows={size}")

    automatic = _refund_candidate(engine)
    result = _decode(tools["evaluate_refund"].invoke(_refund_payload(automatic)))
    _record(
        rows,
        "TS-07",
        "refund auto-resolve candidate",
        result["ok"] and result["data"]["decision"] == "AUTO_RESOLVE",
        f"decision={result.get('data', {}).get('decision')}; eligible={result.get('data', {}).get('eligible')}",
    )
    risky = _refund_candidate(engine, risk=True)
    result = _decode(tools["evaluate_refund"].invoke(_refund_payload(risky)))
    _record(
        rows,
        "TS-08",
        "refund risk escalation",
        result["ok"] and "RISK_FLAGGED" in result["data"]["reason_codes"],
        f"decision={result.get('data', {}).get('decision')}; reason=RISK_FLAGGED",
    )
    expensive = _refund_candidate(engine, minimum_total=501.0)
    result = _decode(tools["evaluate_refund"].invoke(_refund_payload(expensive, 501.0)))
    _record(
        rows,
        "TS-09",
        "refund amount escalation",
        result["ok"] and "AUTO_REFUND_LIMIT_EXCEEDED" in result["data"]["reason_codes"],
        f"decision={result.get('data', {}).get('decision')}; amount=501 BRL",
    )
    incomplete = _refund_payload(automatic)
    incomplete.pop("product_condition_ok")
    result = _decode(tools["evaluate_refund"].invoke(incomplete))
    _record(
        rows,
        "TS-10",
        "refund need-more-info",
        result["ok"] and result["data"]["decision"] == "NEED_MORE_INFO",
        f"missing_fields={result.get('data', {}).get('missing_fields')}",
    )

    create_result = _decode(
        tools["manage_ticket"].invoke(
            {
                "action": "create",
                "customer_id": automatic.customer_id,
                "order_id": automatic.order_id,
                "category": "RETURN_REFUND",
                "priority": "normal",
                "subject": "Stage 4 disposable ticket smoke",
                "notes": "Synthetic smoke data in a disposable database.",
            }
        )
    )
    ticket_id = create_result.get("data", {}).get("ticket_id")
    get_result = _decode(tools["manage_ticket"].invoke({"action": "get", "ticket_id": ticket_id}))
    update_result = _decode(
        tools["manage_ticket"].invoke(
            {
                "action": "update",
                "ticket_id": ticket_id,
                "status": "resolved",
                "decision": "AUTO_RESOLVE",
                "resolution": "Stage 4 smoke complete.",
            }
        )
    )
    _record(
        rows,
        "TS-11",
        "create/read/update ticket",
        create_result["ok"] and get_result["ok"] and update_result["ok"]
        and update_result["data"]["status"] == "resolved",
        f"ticket lifecycle completed; final_status={update_result.get('data', {}).get('status')}",
    )

    result = _decode(
        tools["search_knowledge"].invoke(
            {"query": "What facts and product condition are required for a no-reason return?"}
        )
    )
    ids = [item["document_id"] for item in result.get("data", {}).get("results", [])]
    _record(
        rows,
        "TS-12",
        "valid KnowledgeTool retrieval",
        result["ok"] and "POL-RETURN-001" in ids[:3],
        f"top3={ids[:3]}",
    )
    weak = _decode(
        tools["search_knowledge"].invoke(
            {"query": "quantum chromodynamics neutrino observatory cafeteria menu"}
        )
    )
    weak_safe = isinstance(weak, dict) and "ok" in weak and "error_code" in weak
    weak_outcome = (
        f"error_code={weak.get('error_code')}"
        if not weak.get("ok")
        else f"returned_chunks={len(weak.get('data', {}).get('results', []))}"
    )
    _record(rows, "TS-13", "KnowledgeTool weak evidence", weak_safe, weak_outcome)

    anomaly = _refund_candidate(engine, anomaly=True)
    result = _decode(tools["evaluate_refund"].invoke(_refund_payload(anomaly)))
    _record(
        rows,
        "TS-14",
        "source-quality anomaly escalation",
        result["ok"] and "SOURCE_DATA_QUALITY_ANOMALY" in result["data"]["reason_codes"],
        f"decision={result.get('data', {}).get('decision')}; reason=SOURCE_DATA_QUALITY_ANOMALY",
    )
    return rows


def write_report(rows: list[dict[str, str]], settings: AppSettings) -> None:
    passed = sum(row["status"] == "PASS" for row in rows)
    lines = [
        "# Stage 4 Business Tool Smoke",
        "",
        "## Scope",
        "",
        "The six structured tools were exercised without an LLM. Business mutations ran against a disposable SQLite database; the configured RAGFlow dataset was queried read-only.",
        "",
        "## Result",
        "",
        f"- Passed: {passed}/{len(rows)}",
        f"- Simulation clock: `{settings.simulation_now.isoformat()}`",
        "- Currency: `BRL`",
        "- Secrets and dataset identifiers are intentionally omitted",
        "",
        "| Case | Check | Status | Evidence |",
        "|---|---|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['case_id']} | {row['name']} | {row['status']} | {row['evidence']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "`AUTO_RESOLVE` is only a deterministic automation candidate; this stage does not execute refunds or implement an Agent. The weak-evidence check verifies a safe structured outcome and does not establish a calibrated relevance threshold.",
            "",
        ]
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    settings = AppSettings()
    with tempfile.TemporaryDirectory(prefix="customer-support-stage4-") as temp_dir:
        database_path = Path(temp_dir) / "smoke.db"
        initialize_database(PROCESSED_DATA_DIR, database_path)
        engine = create_sqlite_engine(database_path)
        try:
            rows = run_smoke(engine, settings)
        finally:
            engine.dispose()
    write_report(rows, settings)
    passed = sum(row["status"] == "PASS" for row in rows)
    print(f"Stage 4 tool smoke: {passed}/{len(rows)} passed")
    print(f"Report: {REPORT_PATH}")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
