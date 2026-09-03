"""Thin, Agent-ready LangChain adapters around Stage 4 business services."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ValidationError
from sqlalchemy import Engine

from customer_support_agent.core.config import AppSettings
from customer_support_agent.core.errors import DomainError, ErrorCode, InvalidInputError
from customer_support_agent.core.schemas import (
    CustomerLookupInput,
    CustomerOrdersInput,
    KnowledgeSearchInput,
    OrderLookupInput,
    RefundEvaluationInput,
    TicketCreateInput,
    TicketManageInput,
    TicketUpdateInput,
    ToolEnvelope,
)
from customer_support_agent.db.engine import create_sqlite_engine
from customer_support_agent.services.customer_service import CustomerService
from customer_support_agent.services.knowledge_service import RAGFlowRetrievalClient
from customer_support_agent.services.order_service import OrderService
from customer_support_agent.services.refund_service import RefundDecisionService
from customer_support_agent.services.ticket_service import TicketService


def _envelope(
    *,
    ok: bool,
    data: Any = None,
    error_code: str | None = None,
    message: str,
) -> dict[str, Any]:
    return ToolEnvelope(
        ok=ok,
        data=data,
        error_code=error_code,
        message=message,
    ).model_dump(mode="json")


def _validation_envelope(exc: ValidationError) -> dict[str, Any]:
    fields = sorted(
        {
            ".".join(str(part) for part in error.get("loc", ())) or "input"
            for error in exc.errors()
        }
    )
    suffix = f" Invalid fields: {', '.join(fields)}." if fields else ""
    return _envelope(
        ok=False,
        error_code=ErrorCode.INVALID_INPUT.value,
        message=f"Tool input validation failed.{suffix}",
    )


def _safe_call(handler: Callable[[], Any], success_message: str) -> dict[str, Any]:
    try:
        value = handler()
        data = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
        return _envelope(ok=True, data=data, message=success_message)
    except ValidationError as exc:
        return _validation_envelope(exc)
    except DomainError as exc:
        return _envelope(
            ok=False,
            error_code=exc.code.value,
            message=exc.safe_message,
        )
    except Exception:
        return _envelope(
            ok=False,
            error_code=ErrorCode.DATABASE_ERROR.value,
            message="The tool operation failed safely.",
        )


def _validation_json(exc: ValidationError) -> str:
    """LangChain validates args before the callable; keep that path non-throwing too."""
    return json.dumps(_validation_envelope(exc), ensure_ascii=False)


def create_business_tools(
    engine: Engine | None = None,
    settings: AppSettings | None = None,
    knowledge_client: RAGFlowRetrievalClient | None = None,
) -> list[StructuredTool]:
    """Build six structured tools with shared service dependencies."""
    runtime_settings = settings or AppSettings()
    runtime_engine = engine or create_sqlite_engine(runtime_settings.database_path)
    customers = CustomerService(runtime_engine)
    orders = OrderService(runtime_engine)
    tickets = TicketService(runtime_engine, runtime_settings.simulation_now)
    refunds = RefundDecisionService(runtime_engine, runtime_settings.simulation_now)
    knowledge = knowledge_client or RAGFlowRetrievalClient(runtime_settings)

    def lookup_customer(customer_id: str) -> dict[str, Any]:
        return _safe_call(
            lambda: customers.get_customer_context(customer_id),
            "Customer context retrieved.",
        )

    def lookup_order(order_id: str) -> dict[str, Any]:
        return _safe_call(
            lambda: orders.get_order_context(order_id),
            "Order context retrieved.",
        )

    def list_customer_orders(customer_id: str) -> dict[str, Any]:
        return _safe_call(
            lambda: [row.model_dump(mode="json") for row in orders.list_customer_orders(customer_id)],
            "Customer orders retrieved.",
        )

    def search_knowledge(query: str) -> dict[str, Any]:
        def operation() -> Any:
            result = knowledge.search(query)
            if not result.results:
                from customer_support_agent.core.errors import PolicyEvidenceNotFoundError

                raise PolicyEvidenceNotFoundError()
            return result

        return _safe_call(operation, "Policy evidence retrieved.")

    def evaluate_refund(**kwargs: Any) -> dict[str, Any]:
        return _safe_call(
            lambda: refunds.evaluate(RefundEvaluationInput.model_validate(kwargs)),
            "Refund request evaluated deterministically.",
        )

    def manage_ticket(**kwargs: Any) -> dict[str, Any]:
        def operation() -> Any:
            request = TicketManageInput.model_validate(kwargs)
            values = request.model_dump(mode="json")
            if request.action == "get":
                if not request.ticket_id:
                    raise InvalidInputError("ticket_id is required for action=get.")
                return tickets.get_ticket(request.ticket_id)
            if request.action == "create":
                return tickets.create_ticket(
                    TicketCreateInput.model_validate(
                        {
                            key: values.get(key)
                            for key in (
                                "customer_id",
                                "order_id",
                                "category",
                                "priority",
                                "subject",
                                "notes",
                            )
                        }
                    )
                )
            return tickets.update_ticket(
                TicketUpdateInput.model_validate(
                    {
                        key: values.get(key)
                        for key in ("ticket_id", "status", "decision", "resolution", "notes")
                    }
                )
            )

        return _safe_call(operation, "Ticket operation completed.")

    common = {"handle_validation_error": _validation_json}
    return [
        StructuredTool.from_function(
            func=lookup_customer,
            name="lookup_customer",
            description="Retrieve a customer support profile by exact customer_id.",
            args_schema=CustomerLookupInput,
            **common,
        ),
        StructuredTool.from_function(
            func=lookup_order,
            name="lookup_order",
            description="Retrieve an order with every item, payment, review, and simulated timestamp.",
            args_schema=OrderLookupInput,
            **common,
        ),
        StructuredTool.from_function(
            func=list_customer_orders,
            name="list_customer_orders",
            description="List summary records for every order belonging to a customer.",
            args_schema=CustomerOrdersInput,
            **common,
        ),
        StructuredTool.from_function(
            func=search_knowledge,
            name="search_knowledge",
            description="Retrieve policy evidence from the configured RAGFlow knowledge dataset.",
            args_schema=KnowledgeSearchInput,
            **common,
        ),
        StructuredTool.from_function(
            func=evaluate_refund,
            name="evaluate_refund",
            description="Evaluate refund eligibility and control escalation using canonical deterministic rules.",
            args_schema=RefundEvaluationInput,
            **common,
        ),
        StructuredTool.from_function(
            func=manage_ticket,
            name="manage_ticket",
            description="Create, get, or update a synthetic DemoShop support ticket.",
            args_schema=TicketManageInput,
            **common,
        ),
    ]


def tools_by_name(tools: list[StructuredTool]) -> dict[str, StructuredTool]:
    return {tool.name: tool for tool in tools}
