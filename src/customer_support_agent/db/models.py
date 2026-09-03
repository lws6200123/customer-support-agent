"""SQLAlchemy schema for the Stage 2 operational demo database."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    source_customer_unique_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(40), nullable=False)
    city: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(8), index=True)
    zip_code_prefix: Mapped[str | None] = mapped_column(String(12))
    data_origin: Mapped[str] = mapped_column(String(64), nullable=False)


class CustomerSupportProfile(Base):
    __tablename__ = "customer_support_profiles"

    customer_id: Mapped[str] = mapped_column(
        ForeignKey("customers.customer_id", ondelete="CASCADE"), primary_key=True
    )
    membership_level: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    risk_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    account_status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    identity_verified: Mapped[bool] = mapped_column(Boolean, nullable=False)
    preferred_language: Mapped[str] = mapped_column(String(12), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    data_origin: Mapped[str] = mapped_column(String(64), nullable=False)


class Product(Base):
    __tablename__ = "products"

    product_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    source_product_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    category_name: Mapped[str | None] = mapped_column(String(120), index=True)
    category_name_english: Mapped[str | None] = mapped_column(String(120), index=True)
    name_length: Mapped[int | None] = mapped_column(Integer)
    description_length: Mapped[int | None] = mapped_column(Integer)
    photos_quantity: Mapped[int | None] = mapped_column(Integer)
    weight_g: Mapped[float | None] = mapped_column(Float)
    length_cm: Mapped[float | None] = mapped_column(Float)
    height_cm: Mapped[float | None] = mapped_column(Float)
    width_cm: Mapped[float | None] = mapped_column(Float)
    data_origin: Mapped[str] = mapped_column(String(64), nullable=False)


class Seller(Base):
    __tablename__ = "sellers"

    seller_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    source_seller_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    city: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(8), index=True)
    zip_code_prefix: Mapped[str | None] = mapped_column(String(12))
    data_origin: Mapped[str] = mapped_column(String(64), nullable=False)


class Order(Base):
    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    source_order_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    customer_id: Mapped[str] = mapped_column(
        ForeignKey("customers.customer_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    source_customer_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    source_data_quality_flag: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    scenario_labels: Mapped[str] = mapped_column(Text, nullable=False)
    timeline_offset_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    source_purchase_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    purchase_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source_approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    source_carrier_handoff_at: Mapped[datetime | None] = mapped_column(DateTime)
    carrier_handoff_at: Mapped[datetime | None] = mapped_column(DateTime)
    source_delivered_at: Mapped[datetime | None] = mapped_column(DateTime)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    source_estimated_delivery_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    estimated_delivery_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    data_origin: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (Index("ix_orders_status_quality", "status", "source_data_quality_flag"),)


class OrderItem(Base):
    __tablename__ = "order_items"

    order_item_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.order_id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_order_item_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.product_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    seller_id: Mapped[str] = mapped_column(
        ForeignKey("sellers.seller_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    source_shipping_limit_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    shipping_limit_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    freight_value: Mapped[float] = mapped_column(Float, nullable=False)
    data_origin: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (UniqueConstraint("order_id", "source_order_item_sequence"),)


class Payment(Base):
    __tablename__ = "payments"

    payment_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.order_id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_payment_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_type: Mapped[str] = mapped_column(String(32), nullable=False)
    payment_installments: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_value: Mapped[float] = mapped_column(Float, nullable=False)
    data_origin: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (UniqueConstraint("order_id", "source_payment_sequence"),)


class Review(Base):
    __tablename__ = "reviews"

    review_row_id: Mapped[str] = mapped_column(String(28), primary_key=True)
    source_review_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.order_id", ondelete="CASCADE"), nullable=False, index=True
    )
    review_score: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    review_comment_title: Mapped[str | None] = mapped_column(Text)
    review_comment_message: Mapped[str | None] = mapped_column(Text)
    source_review_created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    review_created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source_review_answered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    review_answered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    data_origin: Mapped[str] = mapped_column(String(64), nullable=False)


class Ticket(Base):
    __tablename__ = "tickets"

    ticket_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), nullable=False, index=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.order_id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(24), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    data_origin: Mapped[str] = mapped_column(String(64), nullable=False)


class Refund(Base):
    __tablename__ = "refunds"

    refund_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.order_id"), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    data_origin: Mapped[str] = mapped_column(String(64), nullable=False)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    agent_run_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.customer_id"), index=True)
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.order_id"), index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)


class AgentStep(Base):
    __tablename__ = "agent_steps"

    agent_step_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_run_id: Mapped[int] = mapped_column(
        ForeignKey("agent_runs.agent_run_id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(40), nullable=False)
    payload_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (UniqueConstraint("agent_run_id", "step_sequence"),)


class Feedback(Base):
    __tablename__ = "feedback"

    feedback_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_run_id: Mapped[int] = mapped_column(
        ForeignKey("agent_runs.agent_run_id", ondelete="CASCADE"), nullable=False, index=True
    )
    rating: Mapped[int | None] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
