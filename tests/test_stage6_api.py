"""Stage 6 API, SSE, review, correlation, and contract tests."""

from __future__ import annotations

import json

import httpx
import pytest
from sqlalchemy import select

from customer_support_agent.agent.schemas import (
    ActionPlan,
    AgentPriority,
    Intent,
    ResponseDraft,
    SubIntent,
    TicketClassification,
)
from customer_support_agent.agent.workflow import SupportAgentWorkflow
from customer_support_agent.api.main import create_app
from customer_support_agent.core.config import AppSettings, PROCESSED_DATA_DIR
from customer_support_agent.core.errors import LLMStructuredOutputError
from customer_support_agent.core.schemas import KnowledgeResponse, KnowledgeResult
from customer_support_agent.db.engine import create_sqlite_engine
from customer_support_agent.db.loader import initialize_database
from customer_support_agent.db.models import Order


pytestmark = pytest.mark.anyio


@pytest.fixture(scope="module")
def anyio_backend():  # type: ignore[no-untyped-def]
    return "asyncio"


class ApiFakeKnowledge:
    def search(self, query: str) -> KnowledgeResponse:
        return KnowledgeResponse(
            query=query,
            results=[
                KnowledgeResult(
                    content="Use verified delivery timestamps and provide neutral guidance.",
                    document_name="02_delivery_policy.md",
                    document_id="POL-DELIVERY-001",
                    local_policy_id="POL-DELIVERY-001",
                    ragflow_document_id="fake-document",
                    chunk_id="fake-chunk",
                    score=0.91,
                    source_type="public_policy_derived",
                    source_organization="public reference",
                )
            ],
        )


class ApiFakeModel:
    def classify(self, message, customer_id, order_id, taxonomy):  # type: ignore[no-untyped-def]
        del taxonomy
        if "escalate" in message.casefold():
            raise LLMStructuredOutputError()
        if "need-info" in message.casefold():
            return TicketClassification(
                intent=Intent.DELIVERY,
                sub_intent=SubIntent.TRACK_DELIVERY,
                priority=AgentPriority.NORMAL,
                customer_id=customer_id,
                order_id=None,
                issue_summary="Order identifier is missing.",
            )
        return TicketClassification(
            intent=Intent.DELIVERY,
            sub_intent=SubIntent.TRACK_DELIVERY,
            priority=AgentPriority.NORMAL,
            customer_id=customer_id,
            order_id=order_id,
            issue_summary="Track a known demo order.",
        )

    def plan(self, state):  # type: ignore[no-untyped-def]
        del state
        return ActionPlan(actions=[], rationale="Deterministic graph selects required tools.")

    def draft(self, state):  # type: ignore[no-untyped-def]
        return ResponseDraft(
            customer_response=(
                "A support specialist should review this request."
                if str(state.get("decision")) == "Decision.ESCALATE_TO_HUMAN"
                else "Verified order information was reviewed; no payment action was executed."
            ),
            agent_summary="Safe fake Agent summary.",
        )


@pytest.fixture(scope="module")
async def api_context(tmp_path_factory):  # type: ignore[no-untyped-def]
    path = tmp_path_factory.mktemp("stage6") / "api.db"
    initialize_database(PROCESSED_DATA_DIR, path)
    engine = create_sqlite_engine(path)
    settings = AppSettings(
        _env_file=None,
        database_path=path,
        cors_allowed_origins="http://localhost:5173",
    )

    def factory() -> SupportAgentWorkflow:
        return SupportAgentWorkflow(
            ApiFakeModel(), engine=engine, settings=settings, knowledge_client=ApiFakeKnowledge()
        )

    app = create_app(settings=settings, engine=engine, workflow_factory=factory)
    with engine.connect() as connection:
        order = connection.execute(select(Order.order_id, Order.customer_id).limit(1)).first()
    assert order is not None
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            yield client, order.order_id, order.customer_id
    engine.dispose()


async def _run(client: httpx.AsyncClient, order_id: str, customer_id: str, message: str):
    return await client.post(
        "/api/v1/agent/run",
        json={"message": message, "order_id": order_id, "customer_id": customer_id},
    )


async def test_health_readiness_request_id_and_no_secret(api_context) -> None:  # type: ignore[no-untyped-def]
    client, _, _ = api_context
    response = await client.get("/health", headers={"X-Request-ID": "stage6-test-id"})
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "stage6-test-id"
    assert response.json()["request_id"] == "stage6-test-id"
    ready = await client.get("/ready")
    assert ready.json()["data"]["database"] == "available"
    assert "api_key" not in ready.text.casefold()


async def test_ticket_list_pagination_create_get_and_missing(api_context) -> None:  # type: ignore[no-untyped-def]
    client, order_id, customer_id = api_context
    created = await client.post(
        "/api/v1/tickets",
        json={"message": "A linked demo support ticket", "order_id": order_id, "customer_id": customer_id},
    )
    assert created.status_code == 201
    ticket_id = created.json()["data"]["ticket_id"]
    listing = await client.get("/api/v1/tickets?page=1&page_size=1")
    assert listing.status_code == 200
    assert listing.json()["data"]["page_size"] == 1
    assert len(listing.json()["data"]["items"]) == 1
    detail = await client.get(f"/api/v1/tickets/{ticket_id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["customer"]["customer_id"] == customer_id
    missing = await client.get("/api/v1/tickets/TKT-NOT-FOUND")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "TICKET_NOT_FOUND"


async def test_ticket_create_requires_real_links_and_error_envelope(api_context) -> None:  # type: ignore[no-untyped-def]
    client, _, _ = api_context
    response = await client.post("/api/v1/tickets", json={"message": "No links"})
    assert response.status_code == 400
    assert response.json()["ok"] is False
    invalid = await client.post("/api/v1/tickets", json={"message": ""})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_non_streaming_auto_resolve_trace_and_ordered_steps(api_context) -> None:  # type: ignore[no-untyped-def]
    client, order_id, customer_id = api_context
    response = await _run(client, order_id, customer_id, "Track this delivery")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["decision"] == "AUTO_RESOLVE"
    assert "no payment action" in data["response"]
    run = await client.get(f"/api/v1/agent-runs/{data['run_id']}")
    assert run.status_code == 200 and run.json()["data"]["decision"] == "AUTO_RESOLVE"
    steps = await client.get(f"/api/v1/agent-runs/{data['run_id']}/steps")
    sequences = [item["sequence"] for item in steps.json()["data"]["items"]]
    assert sequences == sorted(sequences)
    assert len(sequences) >= 8


async def test_need_more_info_unlinked_run(api_context) -> None:  # type: ignore[no-untyped-def]
    client, _, customer_id = api_context
    response = await client.post(
        "/api/v1/agent/run", json={"message": "need-info delivery", "customer_id": customer_id}
    )
    assert response.status_code == 200
    assert response.json()["data"]["decision"] == "NEED_MORE_INFO"
    assert response.json()["data"]["ticket_id"] is None


async def test_escalation_queue_resolve_and_conflict(api_context) -> None:  # type: ignore[no-untyped-def]
    client, order_id, customer_id = api_context
    escalated = await _run(client, order_id, customer_id, "escalate this case")
    data = escalated.json()["data"]
    assert data["decision"] == "ESCALATE_TO_HUMAN"
    queue = await client.get("/api/v1/human-reviews?page=1&page_size=100")
    assert queue.status_code == 200
    ids = {item["ticket_id"] for item in queue.json()["data"]["items"]}
    assert data["ticket_id"] in ids
    resolved = await client.post(
        f"/api/v1/human-reviews/{data['ticket_id']}",
        json={"action": "RESOLVE", "review_note": "Reviewed without financial execution."},
    )
    assert resolved.status_code == 200
    assert resolved.json()["data"]["ticket_status"] == "resolved"
    conflict = await client.post(
        f"/api/v1/human-reviews/{data['ticket_id']}", json={"action": "KEEP_ESCALATED"}
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


async def test_human_request_more_info(api_context) -> None:  # type: ignore[no-untyped-def]
    client, order_id, customer_id = api_context
    data = (await _run(client, order_id, customer_id, "escalate for more context")).json()["data"]
    response = await client.post(
        f"/api/v1/human-reviews/{data['ticket_id']}",
        json={"action": "REQUEST_MORE_INFO"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["ticket_status"] == "awaiting_customer"


def _events(response) -> list[tuple[str, dict]]:  # type: ignore[no-untyped-def]
    blocks = [block for block in response.text.split("\n\n") if block.strip()]
    parsed = []
    for block in blocks:
        lines = block.splitlines()
        parsed.append((lines[0].removeprefix("event: "), json.loads(lines[1].removeprefix("data: "))))
    return parsed


async def test_sse_order_content_type_and_nonstream_parity(api_context) -> None:  # type: ignore[no-untyped-def]
    client, order_id, customer_id = api_context
    payload = {"message": "Track via stream", "order_id": order_id, "customer_id": customer_id}
    normal = (await client.post("/api/v1/agent/run", json=payload)).json()["data"]
    streamed = await client.post("/api/v1/agent/run/stream", json=payload)
    assert streamed.status_code == 200
    assert streamed.headers["content-type"].startswith("text/event-stream")
    events = _events(streamed)
    names = [name for name, _ in events]
    assert names[0] == "run_started"
    assert "classification" in names
    assert "tool_started" in names and "tool_completed" in names
    assert names.index("tool_started") < names.index("tool_completed")
    assert names[-2:] == ["final_response", "run_completed"]
    assert events[-1][1]["decision"] == normal["decision"] == "AUTO_RESOLVE"


async def test_sse_failure_is_safe_error_event(api_context) -> None:  # type: ignore[no-untyped-def]
    client, order_id, customer_id = api_context
    response = await client.post(
        "/api/v1/agent/run/stream",
        json={"message": "track", "order_id": "NOT-FOUND", "customer_id": customer_id},
    )
    assert response.status_code == 200
    events = _events(response)
    assert [name for name, _ in events] == ["error"]
    assert "NOT-FOUND" not in response.text


async def test_dashboard_cors_openapi_and_missing_run(api_context) -> None:  # type: ignore[no-untyped-def]
    client, _, _ = api_context
    dashboard = await client.get("/api/v1/dashboard/summary")
    assert dashboard.status_code == 200
    assert dashboard.json()["data"]["total_tickets"] > 0
    cors = await client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert cors.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert cors.headers.get("access-control-allow-credentials") != "true"
    schema = await client.get("/openapi.json")
    assert schema.status_code == 200
    assert "/api/v1/agent/run/stream" in schema.json()["paths"]
    missing = await client.get("/api/v1/agent-runs/999999999")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "RUN_NOT_FOUND"
