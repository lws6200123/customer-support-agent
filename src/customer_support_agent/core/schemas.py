"""Pydantic contracts shared by Stage 4 services and structured tools."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Decision(str, Enum):
    AUTO_RESOLVE = "AUTO_RESOLVE"
    NEED_MORE_INFO = "NEED_MORE_INFO"
    ESCALATE_TO_HUMAN = "ESCALATE_TO_HUMAN"


class TicketStatus(str, Enum):
    OPEN = "open"
    AWAITING_CUSTOMER = "awaiting_customer"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    CLOSED = "closed"


class CustomerLookupInput(StrictModel):
    customer_id: str = Field(min_length=1, max_length=64)


class OrderLookupInput(StrictModel):
    order_id: str = Field(min_length=1, max_length=64)


class CustomerOrdersInput(StrictModel):
    customer_id: str = Field(min_length=1, max_length=64)


class KnowledgeSearchInput(StrictModel):
    query: str = Field(min_length=2, max_length=1000)


class CustomerContext(BaseModel):
    customer_id: str
    display_name: str
    location: dict[str, str | None]
    membership_level: str
    risk_flag: bool
    account_status: str
    identity_verified: bool
    preferred_language: str


class OrderItemContext(BaseModel):
    order_item_id: str
    source_order_item_sequence: int
    product_id: str
    category_name: str | None
    category_name_english: str | None
    seller_id: str
    seller_city: str | None
    seller_state: str | None
    price: float
    freight_value: float
    shipping_limit_at: datetime


class PaymentContext(BaseModel):
    payment_id: str
    source_payment_sequence: int
    payment_type: str
    payment_installments: int
    payment_value: float


class ReviewContext(BaseModel):
    review_row_id: str
    source_review_id: str
    review_score: int
    review_comment_title: str | None
    review_comment_message: str | None
    review_created_at: datetime
    review_answered_at: datetime


class OrderContext(BaseModel):
    order_id: str
    source_order_id: str
    customer_id: str
    status: str
    source_data_quality_flag: str
    scenario_labels: str
    purchase_at: datetime
    approved_at: datetime | None
    carrier_handoff_at: datetime | None
    delivered_at: datetime | None
    estimated_delivery_at: datetime
    items: list[OrderItemContext]
    payments: list[PaymentContext]
    reviews: list[ReviewContext]
    payment_total: float
    currency: str


class OrderSummary(BaseModel):
    order_id: str
    status: str
    purchase_at: datetime
    delivered_at: datetime | None
    estimated_delivery_at: datetime
    payment_total: float
    currency: str


class TicketCreateInput(StrictModel):
    customer_id: str = Field(min_length=1, max_length=64)
    order_id: str = Field(min_length=1, max_length=64)
    category: str = Field(min_length=1, max_length=64)
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    subject: str = Field(min_length=3, max_length=255)
    notes: str | None = Field(default=None, max_length=4000)


class TicketUpdateInput(StrictModel):
    ticket_id: str = Field(min_length=1, max_length=64)
    status: TicketStatus | None = None
    decision: Decision | None = None
    resolution: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def require_change(self) -> "TicketUpdateInput":
        if all(
            value is None
            for value in (self.status, self.decision, self.resolution, self.notes)
        ):
            raise ValueError("At least one ticket update field is required")
        return self


class TicketManageInput(StrictModel):
    action: Literal["create", "get", "update"]
    ticket_id: str | None = None
    customer_id: str | None = None
    order_id: str | None = None
    category: str | None = None
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    subject: str | None = None
    status: TicketStatus | None = None
    decision: Decision | None = None
    resolution: str | None = None
    notes: str | None = None


class TicketContext(BaseModel):
    ticket_id: str
    customer_id: str
    order_id: str
    category: str
    status: TicketStatus
    decision: Decision | None
    priority: str
    subject: str
    resolution: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    data_origin: str


class RefundReasonCode(str, Enum):
    NO_REASON = "NO_REASON"
    PRODUCT_DEFECT = "PRODUCT_DEFECT"
    DAMAGED_DELIVERY = "DAMAGED_DELIVERY"
    MISSING_ITEM = "MISSING_ITEM"
    WRONG_PRODUCT = "WRONG_PRODUCT"


class RefundEvaluationInput(StrictModel):
    order_id: str | None = Field(default=None, max_length=64)
    reason_code: RefundReasonCode | None = None
    requested_amount: float | None = Field(default=None, gt=0)
    issue_description: str | None = Field(default=None, max_length=4000)
    product_condition_ok: bool | None = None
    defect_confirmed: bool | None = None
    evidence_confirmed: bool | None = None


class RefundDecisionResult(BaseModel):
    decision: Decision
    eligible: bool | None
    reason_codes: list[str]
    human_readable_reasons: list[str]
    policy_requirements: list[str]
    missing_fields: list[str]
    order_id: str | None
    customer_id: str | None
    requested_amount: float | None
    payment_total: float | None
    currency: str
    prior_approved_refunds_in_window: int | None


class KnowledgeResult(BaseModel):
    content: str
    document_name: str
    document_id: str
    local_policy_id: str | None
    ragflow_document_id: str | None
    chunk_id: str
    score: float
    source_type: str | None
    source_organization: str | None


class KnowledgeResponse(BaseModel):
    query: str
    results: list[KnowledgeResult]


class ToolEnvelope(BaseModel):
    ok: bool
    data: Any = None
    error_code: str | None = None
    message: str
