"""Deterministic workflow tests with real graph/tools/rules and a scripted LLM."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import exists, func, select

from customer_support_agent.agent.schemas import (
    ActionPlan,
    AgentAction,
    AgentPriority,
    AgentRequest,
    AgentRunStatus,
    Intent,
    ResponseDraft,
    SubIntent,
    TicketClassification,
)
from customer_support_agent.agent.workflow import SupportAgentWorkflow
from customer_support_agent.core.config import AppSettings, SIMULATION_NOW
from customer_support_agent.core.errors import (
    KnowledgeServiceUnavailableError,
    LLMConfigMissingError,
    LLMStructuredOutputError,
)
from customer_support_agent.core.schemas import (
    Decision,
    KnowledgeResponse,
    KnowledgeResult,
    RefundReasonCode,
    TicketCreateInput,
    TicketStatus,
)
from customer_support_agent.db.engine import create_sqlite_engine
from customer_support_agent.db.loader import initialize_database
from customer_support_agent.db.models import CustomerSupportProfile, Order, Payment, Refund
from customer_support_agent.llm.adapter import DeepSeekChatModel
from customer_support_agent.llm.fake import ScriptedSupportLanguageModel
from customer_support_agent.services.demo_dataset import build_demo_data, write_processed_dataset
from customer_support_agent.services.ticket_service import TicketService
from customer_support_agent.services.trace_service import AgentTraceService
from customer_support_agent.core.security import sanitize_text
from customer_support_agent.services.rules import load_intent_taxonomy


@pytest.fixture(scope="module")
def stage5_engine(tmp_path_factory):
    entities, metadata = build_demo_data()
    root = tmp_path_factory.mktemp("stage5-db")
    processed = root / "processed"
    database = root / "demo.db"
    write_processed_dataset(entities, metadata, processed)
    initialize_database(processed, database)
    engine = create_sqlite_engine(database)
    yield engine
    engine.dispose()


class FakeKnowledgeClient:
    def search(self, query: str) -> KnowledgeResponse:
        return KnowledgeResponse(
            query=query,
            results=[
                KnowledgeResult(
                    content="Use verified order facts and the documented policy window.",
                    document_name="01_return_exchange_policy.md",
                    document_id="POL-RETURN-001",
                    local_policy_id="POL-RETURN-001",
                    ragflow_document_id="test-document",
                    chunk_id="test-chunk",
                    score=0.9,
                    source_type="public_policy_derived",
                    source_organization="JD.com Help Center",
                )
            ],
        )


class FailingKnowledgeClient:
    def search(self, query: str) -> KnowledgeResponse:
        del query
        raise KnowledgeServiceUnavailableError()


def _settings(**updates) -> AppSettings:  # type: ignore[no-untyped-def]
    return AppSettings(_env_file=None, **updates)


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
    assert row is not None
    return row


def _classification(
    intent: Intent,
    sub_intent: str,
    *,
    customer_id: str | None = None,
    order_id: str | None = None,
    amount: float | None = None,
    reason_code: RefundReasonCode | None = RefundReasonCode.NO_REASON,
    product_condition_ok: bool | None = None,
    human_review_requested: bool = False,
    legal_or_regulatory_complaint: bool = False,
    safety_sensitive: bool = False,
) -> TicketClassification:
    refund = intent == Intent.RETURN_REFUND
    return TicketClassification(
        intent=intent,
        sub_intent=sub_intent,
        priority=AgentPriority.NORMAL,
        customer_id=customer_id,
        order_id=order_id,
        issue_summary="Structured test issue summary.",
        reason_code=(reason_code if refund else None),
        requested_amount=amount if refund else None,
        product_condition_ok=(
            product_condition_ok
            if refund and product_condition_ok is not None
            else True if refund else None
        ),
        human_review_requested=human_review_requested,
        legal_or_regulatory_complaint=legal_or_regulatory_complaint,
        safety_sensitive=safety_sensitive,
    )


def _workflow(
    engine,
    classification: TicketClassification | Exception,
    *,
    actions: list[AgentAction] | None = None,
    draft: ResponseDraft | Exception | None = None,
    knowledge=None,  # type: ignore[no-untyped-def]
    settings: AppSettings | None = None,
) -> SupportAgentWorkflow:
    model = ScriptedSupportLanguageModel(
        classifications=[classification],
        plans=[ActionPlan(actions=actions or [], rationale="Scripted safe plan.")],
        drafts=[
            draft
            or ResponseDraft(
                customer_response="We reviewed the verified information. No payment action has been executed.",
                agent_summary="Scripted internal summary.",
            )
        ],
    )
    return SupportAgentWorkflow(
        model,
        engine=engine,
        settings=settings or _settings(),
        knowledge_client=knowledge or FakeKnowledgeClient(),  # type: ignore[arg-type]
    )


def test_refund_auto_resolve_path(stage5_engine) -> None:
    row = _candidate(stage5_engine)
    state = _workflow(
        stage5_engine,
        _classification(
            Intent.RETURN_REFUND,
            "request_refund",
            customer_id=row.customer_id,
            order_id=row.order_id,
            amount=min(float(row.payment_total), 50.0),
        ),
    ).run(AgentRequest(user_message="I want to return this item."))
    assert state["decision"] == Decision.AUTO_RESOLVE
    assert state["refund_result"] is not None and state["refund_result"].eligible is True
    assert AgentAction.EVALUATE_REFUND in state["completed_actions"]


def test_refund_risk_escalation_keeps_neutral_customer_response(stage5_engine) -> None:
    row = _candidate(stage5_engine, risk=True)
    unsafe = ResponseDraft(
        customer_response="You are a risk user and risk_flag caused rejection.",
        agent_summary="Risk control was triggered.",
    )
    state = _workflow(
        stage5_engine,
        _classification(
            Intent.RETURN_REFUND,
            "request_refund",
            customer_id=row.customer_id,
            order_id=row.order_id,
            amount=min(float(row.payment_total), 50.0),
        ),
        draft=unsafe,
    ).run({"user_message": "Please refund this delivered item."})
    assert state["decision"] == Decision.ESCALATE_TO_HUMAN
    assert "risk_flag" not in state["final_response"]
    assert "manual review" in state["final_response"]


def test_refund_amount_escalation(stage5_engine) -> None:
    row = _candidate(stage5_engine, minimum_total=501.0)
    state = _workflow(
        stage5_engine,
        _classification(
            Intent.RETURN_REFUND,
            "request_refund",
            customer_id=row.customer_id,
            order_id=row.order_id,
            amount=501.0,
        ),
    ).run({"user_message": "Return request for 501 BRL."})
    assert state["decision"] == Decision.ESCALATE_TO_HUMAN
    assert "AUTO_REFUND_LIMIT_EXCEEDED" in state["refund_result"].reason_codes


def test_refund_missing_order_routes_need_more_info(stage5_engine) -> None:
    row = _candidate(stage5_engine)
    state = _workflow(
        stage5_engine,
        _classification(
            Intent.RETURN_REFUND,
            "request_refund",
            customer_id=row.customer_id,
            amount=20.0,
        ),
        actions=[AgentAction.EVALUATE_REFUND],
    ).run({"user_message": "I need a refund but did not provide the order."})
    assert state["decision"] == Decision.NEED_MORE_INFO
    assert "order_id" in state["missing_fields"]
    assert AgentAction.EVALUATE_REFUND not in state["completed_actions"]
    assert AgentAction.LIST_CUSTOMER_ORDERS in state["completed_actions"]


@pytest.mark.parametrize(
    ("intent", "sub_intent"),
    [
        (Intent.DELIVERY, "track_delivery"),
        (Intent.INVOICE, "request_invoice"),
    ],
)
def test_order_policy_paths(stage5_engine, intent: Intent, sub_intent: str) -> None:
    row = _candidate(stage5_engine)
    state = _workflow(
        stage5_engine,
        _classification(intent, sub_intent, customer_id=row.customer_id, order_id=row.order_id),
    ).run({"user_message": "Please help with my order."})
    assert state["decision"] == Decision.AUTO_RESOLVE
    assert AgentAction.LOOKUP_ORDER in state["completed_actions"]
    assert AgentAction.SEARCH_KNOWLEDGE in state["completed_actions"]
    assert AgentAction.EVALUATE_REFUND not in state["completed_actions"]


def test_account_path_blocks_refund_action(stage5_engine) -> None:
    row = _candidate(stage5_engine)
    state = _workflow(
        stage5_engine,
        _classification(Intent.ACCOUNT, "account_risk", customer_id=row.customer_id),
        actions=[AgentAction.EVALUATE_REFUND, AgentAction.SEARCH_KNOWLEDGE],
    ).run({"user_message": "I am worried about account security."})
    assert state["decision"] == Decision.AUTO_RESOLVE
    assert AgentAction.EVALUATE_REFUND not in state["planned_actions"]
    assert AgentAction.EVALUATE_REFUND not in state["completed_actions"]


def test_generic_return_normalizes_no_special_reason(stage5_engine) -> None:
    row = _candidate(stage5_engine)
    state = _workflow(
        stage5_engine,
        _classification(
            Intent.RETURN_REFUND,
            "return_product",
            customer_id=row.customer_id,
            order_id=row.order_id,
            amount=min(float(row.payment_total), 20.0),
            reason_code=None,
            product_condition_ok=True,
        ),
    ).run({"user_message": "I want to return the unused complete item."})
    assert state["refund_result"] is not None
    assert "reason_code" not in state["refund_result"].missing_fields


def test_non_refund_source_data_anomaly_escalates(stage5_engine) -> None:
    with stage5_engine.connect() as connection:
        row = connection.execute(
            select(Order.order_id, Order.customer_id)
            .where(Order.source_data_quality_flag != "none")
            .order_by(Order.order_id)
            .limit(1)
        ).one()
    state = _workflow(
        stage5_engine,
        _classification(
            Intent.DELIVERY,
            "track_delivery",
            customer_id=row.customer_id,
            order_id=row.order_id,
        ),
    ).run({"user_message": "The recorded delivery timeline is inconsistent."})
    assert state["order_source_data_quality_flag"] != "none"
    assert state["decision"] == Decision.ESCALATE_TO_HUMAN


@pytest.mark.parametrize(
    ("profile_filter", "sub_intent", "expected", "missing"),
    [
        (CustomerSupportProfile.account_status != "active", "account_locked", Decision.ESCALATE_TO_HUMAN, []),
        (CustomerSupportProfile.risk_flag.is_(True), "account_risk", Decision.ESCALATE_TO_HUMAN, []),
        (
            CustomerSupportProfile.identity_verified.is_(False),
            "password_issue",
            Decision.NEED_MORE_INFO,
            ["identity_verification"],
        ),
    ],
)
def test_account_control_facts_drive_resolution(
    stage5_engine, profile_filter, sub_intent: str, expected: Decision, missing: list[str]
) -> None:
    with stage5_engine.connect() as connection:
        customer_id = connection.scalar(
            select(CustomerSupportProfile.customer_id)
            .where(profile_filter)
            .order_by(CustomerSupportProfile.customer_id)
            .limit(1)
        )
    assert customer_id is not None
    state = _workflow(
        stage5_engine,
        _classification(Intent.ACCOUNT, sub_intent, customer_id=customer_id),
    ).run({"user_message": "Please handle this account security request."})
    assert state["decision"] == expected
    assert state["missing_fields"] == missing


@pytest.mark.parametrize(
    "signal",
    [
        {"human_review_requested": True},
        {"legal_or_regulatory_complaint": True},
        {"safety_sensitive": True},
    ],
)
def test_explicit_escalation_signals_route_to_human(stage5_engine, signal: dict[str, bool]) -> None:
    state = _workflow(
        stage5_engine,
        _classification(Intent.OTHER, "general_question", **signal),
    ).run({"user_message": "This request requires protected human handling."})
    assert state["decision"] == Decision.ESCALATE_TO_HUMAN
    assert state["tool_call_count"] == 0


def test_other_path_uses_no_business_tool(stage5_engine) -> None:
    state = _workflow(
        stage5_engine,
        _classification(Intent.OTHER, "general_question"),
        actions=[AgentAction.EVALUATE_REFUND],
    ).run({"user_message": "Hello, what can you help with?"})
    assert state["decision"] == Decision.AUTO_RESOLVE
    assert state["tool_call_count"] == 0


def test_invalid_llm_structured_output_escalates(stage5_engine) -> None:
    state = _workflow(
        stage5_engine,
        LLMStructuredOutputError(),
    ).run({"user_message": "Ambiguous request."})
    assert state["decision"] == Decision.ESCALATE_TO_HUMAN
    assert "LLM_STRUCTURED_OUTPUT_FAILED" in state["error_codes"]


def test_knowledge_failure_escalates(stage5_engine) -> None:
    row = _candidate(stage5_engine)
    state = _workflow(
        stage5_engine,
        _classification(
            Intent.DELIVERY,
            "track_delivery",
            customer_id=row.customer_id,
            order_id=row.order_id,
        ),
        knowledge=FailingKnowledgeClient(),
    ).run({"user_message": "Where is my order?"})
    assert state["decision"] == Decision.ESCALATE_TO_HUMAN
    assert "KNOWLEDGE_SERVICE_UNAVAILABLE" in state["error_codes"]


def test_order_not_found_is_need_more_info(stage5_engine) -> None:
    state = _workflow(
        stage5_engine,
        _classification(Intent.DELIVERY, "track_delivery", order_id="ORD-NOT-FOUND"),
    ).run({"user_message": "Track order ORD-NOT-FOUND."})
    assert state["decision"] == Decision.NEED_MORE_INFO
    assert "ORDER_NOT_FOUND" in state["error_codes"]


def test_step_limit_escalates_and_bounds_tool_calls(stage5_engine) -> None:
    row = _candidate(stage5_engine)
    state = _workflow(
        stage5_engine,
        _classification(
            Intent.RETURN_REFUND,
            "request_refund",
            customer_id=row.customer_id,
            order_id=row.order_id,
            amount=20.0,
        ),
        settings=_settings(max_agent_steps=1),
    ).run({"user_message": "Refund request."})
    assert state["decision"] == Decision.ESCALATE_TO_HUMAN
    assert state["tool_call_count"] <= 1
    assert "AGENT_STEP_LIMIT_REACHED" in state["error_codes"]


def test_draft_cannot_override_deterministic_refund_result(stage5_engine) -> None:
    row = _candidate(stage5_engine)
    misleading = ResponseDraft(
        customer_response="This needs manual review.",
        agent_summary="The draft prefers escalation.",
    )
    state = _workflow(
        stage5_engine,
        _classification(
            Intent.RETURN_REFUND,
            "request_refund",
            customer_id=row.customer_id,
            order_id=row.order_id,
            amount=min(float(row.payment_total), 50.0),
        ),
        draft=misleading,
    ).run({"user_message": "Eligible refund request."})
    assert state["refund_result"].decision == Decision.AUTO_RESOLVE
    assert state["decision"] == Decision.AUTO_RESOLVE


def test_ticket_lifecycle_and_trace_persistence(stage5_engine) -> None:
    row = _candidate(stage5_engine)
    ticket_service = TicketService(stage5_engine)
    ticket = ticket_service.create_ticket(
        TicketCreateInput(
            customer_id=row.customer_id,
            order_id=row.order_id,
            category="DELIVERY",
            subject="Stage 5 ticket lifecycle test",
        )
    )
    state = _workflow(
        stage5_engine,
        _classification(Intent.DELIVERY, "track_delivery"),
    ).run(
        AgentRequest(
            ticket_id=ticket.ticket_id,
            user_message="Please explain the delivery status.",
        )
    )
    updated = ticket_service.get_ticket(ticket.ticket_id)
    trace = AgentTraceService(stage5_engine).get_trace(state["run_id"])
    assert updated.status == TicketStatus.RESOLVED
    assert updated.decision == Decision.AUTO_RESOLVE
    assert trace.status == AgentRunStatus.COMPLETED
    assert trace.ticket_id == ticket.ticket_id
    assert trace.intent == Intent.DELIVERY.value
    assert trace.decision == Decision.AUTO_RESOLVE
    assert trace.tool_call_count == state["tool_call_count"]
    assert trace.user_message == "Please explain the delivery status."
    assert trace.final_response == state["final_response"]
    assert trace.agent_summary == state["agent_summary"]
    assert [step.step_sequence for step in trace.steps] == list(range(1, len(trace.steps) + 1))
    assert {step.node_name for step in trace.steps} >= {
        "initialize_run",
        "classify_ticket",
        "execute_action",
        "evaluate_resolution",
        "draft_response",
        "persist_result",
    }
    assert all("API_KEY" not in (step.output_summary or "") for step in trace.steps)


def test_deepseek_factory_requires_complete_configuration() -> None:
    with pytest.raises(LLMConfigMissingError):
        DeepSeekChatModel(_settings())


def test_runtime_text_redaction_removes_secret_like_values() -> None:
    redacted = sanitize_text("api_key=super-secret-value password:also-secret")
    assert redacted == "api_key=[REDACTED] password=[REDACTED]"


def test_structured_sub_intent_enum_matches_canonical_taxonomy() -> None:
    configured = {
        value
        for sub_intents in load_intent_taxonomy().values()
        for value in sub_intents
    }
    assert {item.value for item in SubIntent} == configured
