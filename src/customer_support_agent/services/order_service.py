"""Order aggregation service preserving one-to-many business records."""

from __future__ import annotations

from sqlalchemy import Engine, func, select
from sqlalchemy.exc import SQLAlchemyError

from customer_support_agent.core.errors import CustomerNotFoundError, DatabaseError, OrderNotFoundError
from customer_support_agent.core.schemas import OrderContext, OrderSummary
from customer_support_agent.db.models import Customer, Order, Payment
from customer_support_agent.services.rules import load_business_rules
from customer_support_agent.services.support_queries import get_order_details


class OrderService:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.rules = load_business_rules()

    @property
    def currency(self) -> str:
        return str(self.rules["simulation_business"]["currency"])

    def get_order_context(self, order_id: str) -> OrderContext:
        try:
            detail = get_order_details(self.engine, order_id)
        except SQLAlchemyError as exc:
            raise DatabaseError() from exc
        if detail is None:
            raise OrderNotFoundError(order_id)
        detail["currency"] = self.currency
        return OrderContext.model_validate(detail)

    def list_customer_orders(self, customer_id: str) -> list[OrderSummary]:
        try:
            with self.engine.connect() as connection:
                exists = connection.scalar(
                    select(func.count()).select_from(Customer).where(Customer.customer_id == customer_id)
                )
                if not exists:
                    raise CustomerNotFoundError(customer_id)
                rows = connection.execute(
                    select(
                        Order.order_id,
                        Order.status,
                        Order.purchase_at,
                        Order.delivered_at,
                        Order.estimated_delivery_at,
                        func.coalesce(func.sum(Payment.payment_value), 0.0).label("payment_total"),
                    )
                    .outerjoin(Payment, Payment.order_id == Order.order_id)
                    .where(Order.customer_id == customer_id)
                    .group_by(Order.order_id)
                    .order_by(Order.purchase_at.desc(), Order.order_id)
                ).all()
        except CustomerNotFoundError:
            raise
        except SQLAlchemyError as exc:
            raise DatabaseError() from exc
        summaries: list[OrderSummary] = []
        for row in rows:
            values = dict(row._mapping)
            values["payment_total"] = round(float(values["payment_total"]), 2)
            values["currency"] = self.currency
            summaries.append(OrderSummary.model_validate(values))
        return summaries
