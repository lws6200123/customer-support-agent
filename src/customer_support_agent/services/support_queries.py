"""Read-only query functions that exercise the Stage 2 operational schema."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Engine, func, select

from customer_support_agent.core.config import SIMULATION_NOW
from customer_support_agent.db.models import (
    Customer,
    CustomerSupportProfile,
    Order,
    OrderItem,
    Payment,
    Product,
    Review,
    Seller,
)


def _mapping(row) -> dict[str, Any] | None:  # type: ignore[no-untyped-def]
    return dict(row._mapping) if row is not None else None


def get_customer_profile(engine: Engine, customer_id: str) -> dict[str, Any] | None:
    statement = (
        select(
            Customer.customer_id,
            Customer.display_name,
            Customer.city,
            Customer.state,
            Customer.zip_code_prefix,
            CustomerSupportProfile.membership_level,
            CustomerSupportProfile.risk_flag,
            CustomerSupportProfile.account_status,
            CustomerSupportProfile.identity_verified,
            CustomerSupportProfile.preferred_language,
        )
        .join(CustomerSupportProfile, CustomerSupportProfile.customer_id == Customer.customer_id)
        .where(Customer.customer_id == customer_id)
    )
    with engine.connect() as connection:
        return _mapping(connection.execute(statement).first())


def get_order_details(engine: Engine, order_id: str) -> dict[str, Any] | None:
    with engine.connect() as connection:
        order = _mapping(connection.execute(select(Order).where(Order.order_id == order_id)).first())
        if order is None:
            return None
        items = [
            dict(row._mapping)
            for row in connection.execute(
                select(
                    OrderItem.order_item_id,
                    OrderItem.source_order_item_sequence,
                    OrderItem.price,
                    OrderItem.freight_value,
                    OrderItem.shipping_limit_at,
                    Product.product_id,
                    Product.category_name,
                    Product.category_name_english,
                    Seller.seller_id,
                    Seller.city.label("seller_city"),
                    Seller.state.label("seller_state"),
                )
                .join(Product, Product.product_id == OrderItem.product_id)
                .join(Seller, Seller.seller_id == OrderItem.seller_id)
                .where(OrderItem.order_id == order_id)
                .order_by(OrderItem.source_order_item_sequence)
            )
        ]
        payments = [
            dict(row._mapping)
            for row in connection.execute(
                select(
                    Payment.payment_id,
                    Payment.source_payment_sequence,
                    Payment.payment_type,
                    Payment.payment_installments,
                    Payment.payment_value,
                )
                .where(Payment.order_id == order_id)
                .order_by(Payment.source_payment_sequence)
            )
        ]
        reviews = [
            dict(row._mapping)
            for row in connection.execute(
                select(
                    Review.review_row_id,
                    Review.source_review_id,
                    Review.review_score,
                    Review.review_comment_title,
                    Review.review_comment_message,
                    Review.review_created_at,
                    Review.review_answered_at,
                )
                .where(Review.order_id == order_id)
                .order_by(Review.review_row_id)
            )
        ]
    order["items"] = items
    order["payments"] = payments
    order["reviews"] = reviews
    order["payment_total"] = round(sum(float(row["payment_value"]) for row in payments), 2)
    return order


def assess_shipping(
    engine: Engine, order_id: str, simulation_now: datetime = SIMULATION_NOW
) -> dict[str, Any] | None:
    with engine.connect() as connection:
        row = connection.execute(
            select(Order.order_id, Order.status, Order.estimated_delivery_at, Order.source_data_quality_flag)
            .where(Order.order_id == order_id)
        ).first()
    result = _mapping(row)
    if result is None:
        return None
    result["simulation_now"] = simulation_now
    result["overdue"] = (
        result["status"] == "shipped"
        and result["estimated_delivery_at"] is not None
        and result["estimated_delivery_at"] < simulation_now
    )
    return result


def find_late_delivery_order(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return connection.scalar(
            select(Order.order_id)
            .where(
                Order.status == "delivered",
                Order.source_data_quality_flag == "none",
                Order.delivered_at > Order.estimated_delivery_at,
            )
            .order_by(Order.order_id)
            .limit(1)
        )


def find_shipped_orders(engine: Engine) -> list[str]:
    with engine.connect() as connection:
        return list(
            connection.scalars(
                select(Order.order_id)
                .where(Order.status == "shipped", Order.source_data_quality_flag == "none")
                .order_by(Order.order_id)
            )
        )


def find_multi_item_order(engine: Engine) -> tuple[str, int] | None:
    with engine.connect() as connection:
        row = connection.execute(
            select(OrderItem.order_id, func.count().label("row_count"))
            .group_by(OrderItem.order_id)
            .having(func.count() > 1)
            .order_by(OrderItem.order_id)
            .limit(1)
        ).first()
    return (str(row.order_id), int(row.row_count)) if row else None


def find_multi_payment_order(engine: Engine) -> tuple[str, int, float] | None:
    with engine.connect() as connection:
        row = connection.execute(
            select(
                Payment.order_id,
                func.count().label("row_count"),
                func.sum(Payment.payment_value).label("payment_total"),
            )
            .group_by(Payment.order_id)
            .having(func.count() > 1)
            .order_by(Payment.order_id)
            .limit(1)
        ).first()
    return (str(row.order_id), int(row.row_count), round(float(row.payment_total), 2)) if row else None
