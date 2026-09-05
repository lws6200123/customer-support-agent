"""Strict public HTTP contracts for the Stage 6 API."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from customer_support_agent.agent.schemas import AgentPriority, AgentRunStatus, Intent
from customer_support_agent.core.schemas import Decision, TicketStatus


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


DataT = TypeVar("DataT")


class SuccessEnvelope(ApiModel, Generic[DataT]):
    ok: Literal[True] = True
    data: DataT
    request_id: str


class ErrorBody(ApiModel):
    code: str
    message: str


class ErrorEnvelope(ApiModel):
    ok: Literal[False] = False
    error: ErrorBody
    request_id: str


class HealthData(ApiModel):
    status: Literal["ok"] = "ok"
    service: str
    version: str


class ReadinessData(ApiModel):
    status: Literal["ready", "not_ready"]
    database: Literal["available", "unavailable"]
    llm_configured: bool
    ragflow_configured: bool


class TicketCreateRequest(ApiModel):
    message: str = Field(min_length=1, max_length=8000)
    customer_id: str | None = Field(default=None, min_length=1, max_length=64)
    order_id: str | None = Field(default=None, min_length=1, max_length=64)
    priority: Literal["low", "normal", "high", "urgent"] = "normal"


class TicketCreated(ApiModel):
    ticket_id: str
    status: TicketStatus


class TicketListItem(ApiModel):
    ticket_id: str
    customer_id: str
    order_id: str
    category: str
    status: TicketStatus
    decision: Decision | None
    priority: str
    subject: str
    created_at: datetime
    updated_at: datetime


class CustomerSummary(ApiModel):
    customer_id: str
    display_name: str
    city: str | None
    state: str | None


class OrderSummary(ApiModel):
    order_id: str
    status: str
    purchase_at: datetime
    delivered_at: datetime | None
    estimated_delivery_at: datetime
    payment_total: float
    currency: str


class AgentRunSummary(ApiModel):
    run_id: int
    ticket_id: str | None
    intent: Intent | None
    decision: Decision | None
    status: AgentRunStatus
    response: str | None
    agent_summary: str | None
    tool_call_count: int
    latency_ms: float | None
    started_at: datetime
    completed_at: datetime | None


class TicketDetail(ApiModel):
    ticket: TicketListItem
    customer: CustomerSummary | None
    order: OrderSummary | None
    latest_agent_run: AgentRunSummary | None


class TicketPage(ApiModel):
    items: list[TicketListItem]
    page: int
    page_size: int
    total: int


class AgentRunRequest(ApiModel):
    message: str = Field(min_length=1, max_length=8000)
    customer_id: str | None = Field(default=None, min_length=1, max_length=64)
    order_id: str | None = Field(default=None, min_length=1, max_length=64)
    ticket_id: str | None = Field(default=None, min_length=1, max_length=64)


class AgentRunResult(ApiModel):
    run_id: int
    ticket_id: str | None
    intent: Intent | None
    decision: Decision
    ticket_status: TicketStatus | None
    response: str
    agent_summary: str
    tool_call_count: int
    latency_ms: float | None


class TraceStep(ApiModel):
    sequence: int
    node: str
    action: str | None
    tool: str | None
    status: str
    latency_ms: float
    input_summary: str | None
    output_summary: str | None
    error_code: str | None
    created_at: datetime


class TraceSteps(ApiModel):
    run_id: int
    items: list[TraceStep]


class HumanReviewAction(str, Enum):
    RESOLVE = "RESOLVE"
    REQUEST_MORE_INFO = "REQUEST_MORE_INFO"
    KEEP_ESCALATED = "KEEP_ESCALATED"


class HumanReviewItem(ApiModel):
    ticket_id: str
    run_id: int
    intent: Intent | None
    priority: str
    customer: CustomerSummary | None
    order: OrderSummary | None
    agent_summary: str | None
    reason_codes: list[str]
    created_at: datetime


class HumanReviewPage(ApiModel):
    items: list[HumanReviewItem]
    page: int
    page_size: int
    total: int


class HumanReviewRequest(ApiModel):
    action: HumanReviewAction
    review_note: str | None = Field(default=None, max_length=4000)


class HumanReviewResult(ApiModel):
    review_id: int
    ticket_id: str
    action: HumanReviewAction
    ticket_status: TicketStatus
    created_at: datetime


class CountByName(ApiModel):
    name: str
    count: int


class DashboardSummary(ApiModel):
    total_tickets: int
    tickets_by_status: list[CountByName]
    runs_by_decision: list[CountByName]
    auto_resolve_count: int
    need_more_info_count: int
    human_escalation_count: int
    average_agent_latency_ms: float
    recent_runs: list[AgentRunSummary]


class SseEventPayload(ApiModel):
    timestamp: datetime
    run_id: int | None = None
    event: str
    detail: str | None = None
    intent: Intent | None = None
    decision: Decision | None = None
    tool: str | None = None
    tool_ok: bool | None = None
    response: str | None = None
    ticket_id: str | None = None
