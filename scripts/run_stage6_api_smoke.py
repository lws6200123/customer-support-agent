#!/usr/bin/env python3
"""Run a bounded real HTTP smoke against an already-running Stage 6 API."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from customer_support_agent.core.config import AppSettings  # noqa: E402
from customer_support_agent.db.engine import create_sqlite_engine  # noqa: E402
from scripts.run_stage5_agent_smoke import build_cases  # noqa: E402


REPORT_PATH = PROJECT_ROOT / "reports" / "stage6_api_smoke.md"
BASE_URL = "http://127.0.0.1:8000"


def _write_blocked(reason: str) -> None:
    REPORT_PATH.write_text(
        "\n".join(
            [
                "# Stage 6 API Integration Smoke",
                "",
                "## Status",
                "",
                "**BLOCKED — not executed.**",
                "",
                f"Reason: `{reason}`.",
                "",
                "No result was fabricated and no credential value was written to this report.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _parse_sse(text: str) -> list[tuple[str, dict[str, object]]]:
    events: list[tuple[str, dict[str, object]]] = []
    for block in text.split("\n\n"):
        lines = block.strip().splitlines()
        if len(lines) < 2 or not lines[0].startswith("event: "):
            continue
        payload = json.loads(lines[1].removeprefix("data: "))
        events.append((lines[0].removeprefix("event: "), payload))
    return events


def main() -> int:
    settings = AppSettings()
    if not settings.deepseek_configured or not settings.ragflow_configured:
        _write_blocked("LLM_OR_RAGFLOW_CONFIGURATION_MISSING")
        print("Stage 6 API smoke: BLOCKED (LLM or RAGFlow configuration missing)")
        return 2
    engine = create_sqlite_engine(settings.database_path)
    cases = {case["case_id"]: case for case in build_cases(engine)}
    engine.dispose()
    selected = [cases[case_id] for case_id in ("AS-01", "AS-02", "AS-03")]
    rows: list[dict[str, object]] = []
    try:
        with httpx.Client(base_url=BASE_URL, timeout=180.0, trust_env=False) as client:
            health = client.get("/health")
            if health.status_code != 200:
                _write_blocked(f"HEALTH_HTTP_{health.status_code}")
                print(f"Stage 6 API smoke: BLOCKED (health status {health.status_code})")
                return 2
            for case in selected:
                request = case["request"]
                response = client.post(
                    "/api/v1/agent/run",
                    json={
                        "message": request.user_message,
                        "customer_id": request.customer_id,
                        "order_id": request.order_id,
                        "ticket_id": request.ticket_id,
                    },
                )
                body = response.json()
                data = body.get("data", {}) if isinstance(body, dict) else {}
                decision = data.get("decision") if isinstance(data, dict) else None
                rows.append(
                    {
                        "case": case["case_id"],
                        "status": response.status_code,
                        "decision": decision or "none",
                        "expected": case["expected_decision"],
                        "latency": float(data.get("latency_ms") or 0.0) if isinstance(data, dict) else 0.0,
                        "passed": response.status_code == 200 and decision == case["expected_decision"],
                    }
                )
            stream_case = cases["AS-04"]
            request = stream_case["request"]
            streamed = client.post(
                "/api/v1/agent/run/stream",
                json={
                    "message": request.user_message,
                    "customer_id": request.customer_id,
                    "order_id": request.order_id,
                },
            )
            events = _parse_sse(streamed.text)
    except httpx.RequestError:
        _write_blocked("LOCAL_API_UNREACHABLE")
        print("Stage 6 API smoke: BLOCKED (local API unreachable)")
        return 2
    event_types = [event for event, _ in events]
    final_decision = next(
        (payload.get("decision") for event, payload in reversed(events) if event == "run_completed"),
        None,
    )
    sse_passed = (
        streamed.status_code == 200
        and event_types[:2] == ["run_started", "classification"]
        and "tool_started" in event_types
        and "tool_completed" in event_types
        and event_types[-2:] == ["final_response", "run_completed"]
        and final_decision == stream_case["expected_decision"]
    )
    lines = [
        "# Stage 6 API Integration Smoke",
        "",
        "## Scope",
        "",
        "Bounded localhost HTTP smoke through FastAPI, LangGraph, DeepSeek, Stage 4 tools, SQLite, and RAGFlow. This is not a final evaluation benchmark and performs no financial refund.",
        "",
        "## Non-streaming Results",
        "",
        "| Case | Endpoint | HTTP | Decision | Expected | Agent latency ms | Result |",
        "|---|---|---:|---|---|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['case']} | `POST /api/v1/agent/run` | {row['status']} | "
            f"{row['decision']} | {row['expected']} | {row['latency']:.1f} | "
            f"{'PASS' if row['passed'] else 'FAIL'} |"
        )
    lines.extend(
        [
            "",
            "## SSE Result",
            "",
            f"- Endpoint: `POST /api/v1/agent/run/stream`",
            f"- HTTP status: `{streamed.status_code}`",
            f"- Final decision: `{final_decision or 'none'}`",
            f"- Event types: `{', '.join(event_types)}`",
            f"- Result: `{'PASS' if sse_passed else 'FAIL'}`",
            "",
            "## Safety",
            "",
            "Secrets, full prompts, policy bodies, customer identifiers, order identifiers, and dataset identifiers are omitted. AUTO_RESOLVE is only a decision candidate; no refund was executed.",
            "",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    passed = all(bool(row["passed"]) for row in rows) and sse_passed
    print(f"Stage 6 API smoke: {'PASS' if passed else 'FAIL'}")
    print(f"Report: {REPORT_PATH}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
