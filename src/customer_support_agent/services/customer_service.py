"""Customer context service backed by the Stage 2 SQLite database."""

from __future__ import annotations

from sqlalchemy import Engine, select
from sqlalchemy.exc import SQLAlchemyError

from customer_support_agent.core.errors import CustomerNotFoundError, DatabaseError
from customer_support_agent.core.schemas import CustomerContext
from customer_support_agent.db.models import Customer, CustomerSupportProfile


class CustomerService:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def get_customer_context(self, customer_id: str) -> CustomerContext:
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
        try:
            with self.engine.connect() as connection:
                row = connection.execute(statement).first()
        except SQLAlchemyError as exc:
            raise DatabaseError() from exc
        if row is None:
            raise CustomerNotFoundError(customer_id)
        values = row._mapping
        return CustomerContext(
            customer_id=values["customer_id"],
            display_name=values["display_name"],
            location={
                "city": values["city"],
                "state": values["state"],
                "zip_code_prefix": values["zip_code_prefix"],
            },
            membership_level=values["membership_level"],
            risk_flag=bool(values["risk_flag"]),
            account_status=values["account_status"],
            identity_verified=bool(values["identity_verified"]),
            preferred_language=values["preferred_language"],
        )
