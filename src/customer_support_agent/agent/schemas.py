"""Typed contracts for the Stage 5 LangGraph workflow."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TypedDict

from typing_extensions import NotRequired

from pydantic import BaseModel, ConfigDict, Field, model_validator

from customer_support_agent.core.schemas import Decision, RefundDecisionResult, RefundReasonCode


class AgentStrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Intent(str, Enum):
    RETURN_REFUND = "RETURN_REFUND"
    DELIVERY = "DELIVERY"
    PRODUCT_AFTER_SALES = "PRODUCT_AFTER_SALES"
    ACCOUNT = "ACCOUNT"
    INVOICE = "INVOICE"
    OTHER = "OTHER"


class SubIntent(str, Enum):
    REQUEST_REFUND = "request_refund"
    REFUND_STATUS = "refund_status"
    RETURN_PRODUCT = "return_product"
    EXCHANGE_PRODUCT = "exchange_product"
    TRACK_DELIVERY = "track_delivery"
    DELAYED_DELIVERY = "delayed_delivery"
    DAMAGED_DELIVERY = "damaged_delivery"
    MISSING_ITEM = "missing_item"
    PRODUCT_DEFECT = "product_defect"
    WARRANTY_QUESTION = "warranty_question"
    REPAIR_REQUEST = "repair_request"
    ACCOUNT_RISK = "account_risk"
    ACCOUNT_LOCKED = "account_locked"
    PASSWORD_ISSUE = "password_issue"
    REQUEST_INVOICE = "request_invoice"
    MODIFY_INVOICE = "modify_invoice"
    INVOICE_ISSUE = "invoice_issue"
    GENERAL_QUESTION = "general_question"


class AgentPriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class AgentAction(str, Enum):
    LOOKUP_CUSTOMER = "LOOKUP_CUSTOMER"
    LOOKUP_ORDER = "LOOKUP_ORDER"
    LIST_CUSTOMER_ORDERS = "LIST_CUSTOMER_ORDERS"
    SEARCH_KNOWLEDGE = "SEARCH_KNOWLEDGE"
    EVALUATE_REFUND = "EVALUATE_REFUND"


class AgentRunStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ESCALATED = "ESCALATED"
    NEED_MORE_INFO = "NEED_MORE_INFO"


class AgentRequest(AgentStrictModel):
    user_message: str = Field(min_length=1, max_length=8000)
    ticket_id: str | None = Field(default=None, max_length=64)
    customer_id: str | None = Field(default=None, max_length=64)
    order_id: str | None = Field(default=None, max_length=64)


class TicketClassification(AgentStrictModel):
    intent: Intent
    sub_intent: SubIntent
    priority: AgentPriority
    customer_id: str | None = Field(default=None, max_length=64)
    order_id: str | None = Field(default=None, max_length=64)
    issue_summary: str = Field(min_length=1, max_length=1000)
    reason_code: RefundReasonCode | None = None
    requested_amount: float | None = Field(default=None, gt=0)
    product_condition_ok: bool | None = None
    defect_confirmed: bool | None = None
    evidence_confirmed: bool | None = None


class ActionPlan(AgentStrictModel):
    actions: list[AgentAction] = Field(default_factory=list, max_length=8)
    rationale: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def unique_actions(self) -> "ActionPlan":
        if len(self.actions) != len(set(self.actions)):
            raise ValueError("Action plan contains duplicate actions")
        return self


class ResponseDraft(AgentStrictModel):
    customer_response: str = Field(min_length=1, max_length=4000)
    agent_summary: str = Field(min_length=1, max_length=4000)


class ToolExecutionRecord(BaseModel):
    action: AgentAction
    tool_name: str
    ok: bool
    error_code: str | None
    summary: str
    latency_ms: float


class PolicyEvidenceRecord(BaseModel):
    document_id: str
    document_name: str
    chunk_id: str
    score: float
    content: str
    source_type: str | None
    source_organization: str | None


class AgentTraceStep(BaseModel):
    step_sequence: int
    node_name: str
    action: str | None
    tool_name: str | None
    status: str
    latency_ms: float
    input_summary: str | None
    output_summary: str | None
    error_code: str | None
    created_at: datetime


class AgentTrace(BaseModel):
    agent_run_id: int
    ticket_id: str | None
    customer_id: str | None
    order_id: str | None
    user_message: str
    intent: str | None
    decision: Decision | None
    status: AgentRunStatus
    started_at: datetime
    completed_at: datetime | None
    total_latency_ms: float | None
    tool_call_count: int
    error_summary: str | None
    final_response: str | None
    agent_summary: str | None
    steps: list[AgentTraceStep]


class AgentState(TypedDict, total=False):
    run_id: int
    run_status: AgentRunStatus
    ticket_id: str | None
    user_message: str
    customer_id: str | None
    order_id: str | None
    classification: TicketClassification
    intent: Intent
    sub_intent: str
    priority: AgentPriority
    issue_summary: str
    planned_actions: list[AgentAction]
    completed_actions: list[AgentAction]
    pending_actions: list[AgentAction]
    tool_results: list[ToolExecutionRecord]
    policy_evidence: list[PolicyEvidenceRecord]
    refund_result: RefundDecisionResult | None
    decision: Decision | None
    missing_fields: list[str]
    response_type: Decision | None
    final_response: str | None
    agent_summary: str | None
    error_codes: list[str]
    step_count: int
    max_steps: int
    tool_call_count: int
    started_at: datetime
    completed_at: datetime | None
    total_latency_ms: float | None
    fatal_error: NotRequired[bool]
