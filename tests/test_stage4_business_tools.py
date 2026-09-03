"""High-value unit and integration-at-SQLite tests for Stage 4."""

from __future__ import annotations

import json
from datetime import timedelta

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import delete, exists, func, insert, select

from customer_support_agent.core.config import AppSettings, SIMULATION_NOW
from customer_support_agent.core.errors import (
    CustomerNotFoundError,
    KnowledgeServiceUnavailableError,
)
from customer_support_agent.core.schemas import (
    Decision,
    KnowledgeResponse,
    KnowledgeResult,
    RefundEvaluationInput,
    RefundReasonCode,
    TicketCreateInput,
    TicketStatus,
    TicketUpdateInput,
)
from customer_support_agent.db.engine import create_sqlite_engine
from customer_support_agent.db.loader import initialize_database
from customer_support_agent.db.models import (
    Customer,
    CustomerSupportProfile,
    Order,
    Payment,
    Refund,
)
from customer_support_agent.services.customer_service import CustomerService
from customer_support_agent.services.demo_dataset import build_demo_data, write_processed_dataset
from customer_support_agent.services.knowledge_service import RAGFlowRetrievalClient
from customer_support_agent.services.order_service import OrderService
from customer_support_agent.services.refund_service import RefundDecisionService
from customer_support_agent.services.rules import load_business_rules, resolve_rule_reference
from customer_support_agent.services.ticket_service import TicketService
from customer_support_agent.tools import create_business_tools, tools_by_name


@pytest.fixture(scope="module")
def stage4_engine(tmp_path_factory):
    entities, metadata = build_demo_data()
    root = tmp_path_factory.mktemp("stage4-db")
    processed = root / "processed"
    database = root / "demo.db"
    write_processed_dataset(entities, metadata, processed)
    initialize_database(processed, database)
    engine = create_sqlite_engine(database)
    yield engine
    engine.dispose()


def _refund_candidate(engine, *, risk: bool = False, minimum_total: float = 0.0, anomaly: bool = False):
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
            (Order.source_data_quality_flag != "none") if anomaly else (Order.source_data_quality_flag == "none"),
            ~prior_refund,
        )
        .group_by(Order.order_id)
        .having(func.sum(Payment.payment_value) >= minimum_total)
        .order_by(Order.order_id)
        .limit(1)
    )
    with engine.connect() as connection:
        row = connection.execute(statement).first()
    assert row is not None
    return row


def _refund_input(order_id: str, amount: float) -> RefundEvaluationInput:
    return RefundEvaluationInput(
        order_id=order_id,
        reason_code=RefundReasonCode.NO_REASON,
        requested_amount=amount,
        issue_description="Customer requests a return within the policy window.",
        product_condition_ok=True,
    )


def test_business_rules_define_single_currency_and_frequency_semantics() -> None:
    rules = load_business_rules()
    assert rules["simulation_business"]["currency"] == "BRL"
    assert rules["currency_semantics"]["conversion_applied"] is False
    semantics = rules["refund_frequency_semantics"]
    assert semantics["counted_statuses"] == ["approved"]
    assert semantics["current_request_included"] is False
    assert semantics["window_start_inclusive"] is True
    assert semantics["window_end_exclusive"] is True
    assert semantics["automatic_candidate_operator"] == "strictly_less_than"
    assert resolve_rule_reference(rules, semantics["maximum_ref"]) == 2


def test_customer_service_success_and_domain_not_found(stage4_engine) -> None:
    with stage4_engine.connect() as connection:
        customer_id = connection.scalar(select(Customer.customer_id).limit(1))
    result = CustomerService(stage4_engine).get_customer_context(customer_id)
    assert result.customer_id == customer_id
    assert result.location["state"]
    with pytest.raises(CustomerNotFoundError):
        CustomerService(stage4_engine).get_customer_context("CUST-NOT-FOUND")


def test_order_service_preserves_multi_rows_and_lists_orders(stage4_engine) -> None:
    multi_item = (
        select(Order.order_id)
        .where(Order.scenario_labels.contains("multi_item"))
        .order_by(Order.order_id)
        .limit(1)
    )
    with stage4_engine.connect() as connection:
        order_id = connection.scalar(multi_item)
    detail = OrderService(stage4_engine).get_order_context(order_id)
    assert len(detail.items) > 1
    assert detail.payment_total == round(sum(row.payment_value for row in detail.payments), 2)
    summaries = OrderService(stage4_engine).list_customer_orders(detail.customer_id)
    assert detail.order_id in {row.order_id for row in summaries}
    assert all(row.currency == "BRL" for row in summaries)


def test_ticket_service_validates_crud_and_transition(stage4_engine) -> None:
    candidate = _refund_candidate(stage4_engine)
    service = TicketService(stage4_engine)
    created = service.create_ticket(
        TicketCreateInput(
            customer_id=candidate.customer_id,
            order_id=candidate.order_id,
            category="RETURN_REFUND",
            subject="Return request needs review",
        )
    )
    assert created.status == TicketStatus.OPEN
    assert created.data_origin == "synthetic_operational_data"
    updated = service.update_ticket(
        TicketUpdateInput(
            ticket_id=created.ticket_id,
            status=TicketStatus.RESOLVED,
            decision=Decision.AUTO_RESOLVE,
            resolution="Validated deterministic test resolution.",
        )
    )
    assert updated.status == TicketStatus.RESOLVED
    assert service.get_ticket(created.ticket_id).decision == Decision.AUTO_RESOLVE


def test_refund_decisions_keep_eligibility_separate_from_controls(stage4_engine) -> None:
    service = RefundDecisionService(stage4_engine)
    clean = _refund_candidate(stage4_engine)
    automatic = service.evaluate(_refund_input(clean.order_id, min(float(clean.payment_total), 50.0)))
    assert automatic.eligible is True
    assert automatic.decision == Decision.AUTO_RESOLVE

    risky = _refund_candidate(stage4_engine, risk=True)
    risk_result = service.evaluate(_refund_input(risky.order_id, min(float(risky.payment_total), 50.0)))
    assert risk_result.eligible is True
    assert risk_result.decision == Decision.ESCALATE_TO_HUMAN
    assert "RISK_FLAGGED" in risk_result.reason_codes

    expensive = _refund_candidate(stage4_engine, minimum_total=501.0)
    amount_result = service.evaluate(_refund_input(expensive.order_id, 501.0))
    assert amount_result.eligible is True
    assert amount_result.decision == Decision.ESCALATE_TO_HUMAN
    assert "AUTO_REFUND_LIMIT_EXCEEDED" in amount_result.reason_codes

    incomplete = service.evaluate(
        RefundEvaluationInput(
            order_id=clean.order_id,
            reason_code=RefundReasonCode.PRODUCT_DEFECT,
            requested_amount=20.0,
            issue_description="Product does not work.",
        )
    )
    assert incomplete.decision == Decision.NEED_MORE_INFO
    assert incomplete.eligible is None
    assert incomplete.missing_fields == ["defect_confirmed"]

    anomaly = _refund_candidate(stage4_engine, anomaly=True)
    anomaly_result = service.evaluate(
        _refund_input(anomaly.order_id, min(float(anomaly.payment_total), 50.0))
    )
    assert anomaly_result.decision == Decision.ESCALATE_TO_HUMAN
    assert "SOURCE_DATA_QUALITY_ANOMALY" in anomaly_result.reason_codes


def test_refund_frequency_uses_inclusive_start_exclusive_end(stage4_engine) -> None:
    candidate = _refund_candidate(stage4_engine)
    identifiers = ["RFD-TST-BOUNDARY-01", "RFD-TST-BOUNDARY-02", "RFD-TST-BOUNDARY-03"]
    rows = [
        {
            "refund_id": identifiers[0],
            "order_id": candidate.order_id,
            "customer_id": candidate.customer_id,
            "amount": 1.0,
            "reason": "test",
            "status": "approved",
            "requested_at": SIMULATION_NOW - timedelta(days=30),
            "resolved_at": SIMULATION_NOW - timedelta(days=29),
            "data_origin": "synthetic_operational_data",
        },
        {
            "refund_id": identifiers[1],
            "order_id": candidate.order_id,
            "customer_id": candidate.customer_id,
            "amount": 1.0,
            "reason": "test",
            "status": "approved",
            "requested_at": SIMULATION_NOW - timedelta(seconds=1),
            "resolved_at": SIMULATION_NOW,
            "data_origin": "synthetic_operational_data",
        },
        {
            "refund_id": identifiers[2],
            "order_id": candidate.order_id,
            "customer_id": candidate.customer_id,
            "amount": 1.0,
            "reason": "test",
            "status": "approved",
            "requested_at": SIMULATION_NOW,
            "resolved_at": None,
            "data_origin": "synthetic_operational_data",
        },
    ]
    try:
        with stage4_engine.begin() as connection:
            connection.execute(insert(Refund), rows)
        result = RefundDecisionService(stage4_engine).evaluate(
            _refund_input(candidate.order_id, min(float(candidate.payment_total), 50.0))
        )
        assert result.prior_approved_refunds_in_window == 2
        assert result.decision == Decision.ESCALATE_TO_HUMAN
        assert "REFUND_FREQUENCY_LIMIT_REACHED" in result.reason_codes
    finally:
        with stage4_engine.begin() as connection:
            connection.execute(delete(Refund).where(Refund.refund_id.in_(identifiers)))


def _ragflow_settings() -> AppSettings:
    return AppSettings(
        _env_file=None,
        ragflow_base_url="http://ragflow.test",
        ragflow_api_key=SecretStr("unit-test-placeholder"),
        ragflow_dataset_id="dataset-test-id",
    )


def test_ragflow_client_success_and_metadata_normalization() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/retrieval"
        assert request.headers["Authorization"].startswith("Bearer ")
        payload = json.loads(request.content)
        assert payload["page_size"] == 5
        assert payload["similarity_threshold"] == 0.2
        assert "rerank_id" not in payload
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "chunks": [
                        {
                            "id": "chunk-1",
                            "document_id": "ragflow-doc-1",
                            "docnm_kwd": "01_return_exchange_policy.md",
                            "content_with_weight": "Return policy evidence.",
                            "similarity": 0.88,
                        }
                    ]
                },
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    result = RAGFlowRetrievalClient(_ragflow_settings(), client).search("return policy")
    assert result.results[0].document_id == "POL-RETURN-001"
    assert result.results[0].ragflow_document_id == "ragflow-doc-1"
    assert result.results[0].source_type == "public_policy_derived"
    assert result.results[0].score == pytest.approx(0.88)
    client.close()


def test_ragflow_client_normalizes_transport_and_protocol_failure() -> None:
    failing = httpx.Client(
        transport=httpx.MockTransport(lambda _request: httpx.Response(503, text="unavailable"))
    )
    with pytest.raises(KnowledgeServiceUnavailableError):
        RAGFlowRetrievalClient(_ragflow_settings(), failing).search("refund")
    failing.close()

    invalid = httpx.Client(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={"code": 0, "data": {}}))
    )
    with pytest.raises(KnowledgeServiceUnavailableError):
        RAGFlowRetrievalClient(_ragflow_settings(), invalid).search("refund")
    invalid.close()


class _FakeKnowledgeClient:
    def search(self, query: str) -> KnowledgeResponse:
        return KnowledgeResponse(
            query=query,
            results=[
                KnowledgeResult(
                    content="evidence",
                    document_name="01_return_exchange_policy.md",
                    document_id="POL-RETURN-001",
                    local_policy_id="POL-RETURN-001",
                    ragflow_document_id="placeholder",
                    chunk_id="chunk",
                    score=0.9,
                    source_type="public_policy_derived",
                    source_organization="JD.com Help Center",
                )
            ],
        )


def test_structured_tool_envelopes_and_error_normalization(stage4_engine) -> None:
    tools = tools_by_name(
        create_business_tools(engine=stage4_engine, knowledge_client=_FakeKnowledgeClient())  # type: ignore[arg-type]
    )
    assert set(tools) == {
        "lookup_customer",
        "lookup_order",
        "list_customer_orders",
        "search_knowledge",
        "evaluate_refund",
        "manage_ticket",
    }
    with stage4_engine.connect() as connection:
        customer_id = connection.scalar(select(Customer.customer_id).limit(1))
    success = tools["lookup_customer"].invoke({"customer_id": customer_id})
    assert success["ok"] is True and success["error_code"] is None
    missing = tools["lookup_customer"].invoke({"customer_id": "CUST-NOT-FOUND"})
    assert missing["ok"] is False and missing["error_code"] == "CUSTOMER_NOT_FOUND"
    invalid = json.loads(tools["lookup_customer"].invoke({}))
    assert invalid["ok"] is False and invalid["error_code"] == "INVALID_INPUT"
    knowledge = tools["search_knowledge"].invoke({"query": "return policy"})
    assert knowledge["ok"] is True
