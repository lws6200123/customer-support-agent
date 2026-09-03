"""Validated ticket CRUD service for synthetic DemoShop operations."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Engine, insert, select, update
from sqlalchemy.exc import SQLAlchemyError

from customer_support_agent.core.config import SIMULATION_NOW
from customer_support_agent.core.errors import (
    CustomerNotFoundError,
    DatabaseError,
    InvalidInputError,
    OrderNotFoundError,
    TicketNotFoundError,
)
from customer_support_agent.core.schemas import (
    TicketContext,
    TicketCreateInput,
    TicketUpdateInput,
)
from customer_support_agent.db.models import Customer, Order, Ticket
from customer_support_agent.services.rules import load_business_rules, load_intent_taxonomy


class TicketService:
    def __init__(self, engine: Engine, clock: datetime = SIMULATION_NOW) -> None:
        self.engine = engine
        self.clock = clock
        self.rules = load_business_rules()
        self.taxonomy = load_intent_taxonomy()

    def _get_row(self, connection, ticket_id: str):  # type: ignore[no-untyped-def]
        return connection.execute(
            select(Ticket.__table__).where(Ticket.ticket_id == ticket_id)
        ).mappings().first()

    def get_ticket(self, ticket_id: str) -> TicketContext:
        try:
            with self.engine.connect() as connection:
                row = self._get_row(connection, ticket_id)
        except SQLAlchemyError as exc:
            raise DatabaseError() from exc
        if row is None:
            raise TicketNotFoundError(ticket_id)
        return TicketContext.model_validate(dict(row))

    def create_ticket(self, request: TicketCreateInput) -> TicketContext:
        if request.category not in self.taxonomy:
            raise InvalidInputError(f"Unsupported ticket category: {request.category}")
        ticket_id = f"TKT-{uuid4().hex[:16].upper()}"
        initial_status = self.rules["ticket_operations"]["initial_status"]
        values = {
            "ticket_id": ticket_id,
            "customer_id": request.customer_id,
            "order_id": request.order_id,
            "category": request.category,
            "status": initial_status,
            "decision": None,
            "priority": request.priority,
            "subject": request.subject,
            "resolution": None,
            "notes": request.notes,
            "created_at": self.clock,
            "updated_at": self.clock,
            "closed_at": None,
            "data_origin": "synthetic_operational_data",
        }
        try:
            with self.engine.begin() as connection:
                if connection.scalar(
                    select(Customer.customer_id).where(Customer.customer_id == request.customer_id)
                ) is None:
                    raise CustomerNotFoundError(request.customer_id)
                order_customer = connection.scalar(
                    select(Order.customer_id).where(Order.order_id == request.order_id)
                )
                if order_customer is None:
                    raise OrderNotFoundError(request.order_id)
                if order_customer != request.customer_id:
                    raise InvalidInputError("The order does not belong to the supplied customer.")
                connection.execute(insert(Ticket), values)
        except (CustomerNotFoundError, OrderNotFoundError, InvalidInputError):
            raise
        except SQLAlchemyError as exc:
            raise DatabaseError() from exc
        return self.get_ticket(ticket_id)

    def update_ticket(self, request: TicketUpdateInput) -> TicketContext:
        try:
            with self.engine.begin() as connection:
                current = self._get_row(connection, request.ticket_id)
                if current is None:
                    raise TicketNotFoundError(request.ticket_id)
                changes = request.model_dump(exclude={"ticket_id"}, exclude_none=True, mode="json")
                if "status" in changes and changes["status"] != current["status"]:
                    allowed = self.rules["ticket_operations"]["allowed_transitions"].get(
                        current["status"], []
                    )
                    if changes["status"] not in allowed:
                        raise InvalidInputError(
                            f"Invalid ticket transition: {current['status']} -> {changes['status']}"
                        )
                    if changes["status"] == "closed":
                        changes["closed_at"] = self.clock
                    elif current["status"] == "closed":
                        changes["closed_at"] = None
                if "decision" in changes and changes["decision"] not in self.rules["decisions"]:
                    raise InvalidInputError(f"Unsupported ticket decision: {changes['decision']}")
                changes["updated_at"] = self.clock
                connection.execute(
                    update(Ticket).where(Ticket.ticket_id == request.ticket_id).values(**changes)
                )
        except (TicketNotFoundError, InvalidInputError):
            raise
        except SQLAlchemyError as exc:
            raise DatabaseError() from exc
        return self.get_ticket(request.ticket_id)
