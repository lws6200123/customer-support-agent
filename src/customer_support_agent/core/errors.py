"""Domain-safe errors exposed by Stage 4 services and tools."""

from __future__ import annotations

from enum import Enum


class ErrorCode(str, Enum):
    CUSTOMER_NOT_FOUND = "CUSTOMER_NOT_FOUND"
    ORDER_NOT_FOUND = "ORDER_NOT_FOUND"
    TICKET_NOT_FOUND = "TICKET_NOT_FOUND"
    INVALID_INPUT = "INVALID_INPUT"
    DATABASE_ERROR = "DATABASE_ERROR"
    KNOWLEDGE_SERVICE_UNAVAILABLE = "KNOWLEDGE_SERVICE_UNAVAILABLE"
    KNOWLEDGE_CONFIG_MISSING = "KNOWLEDGE_CONFIG_MISSING"
    POLICY_EVIDENCE_NOT_FOUND = "POLICY_EVIDENCE_NOT_FOUND"


class DomainError(RuntimeError):
    """Expected failure that can be safely normalized for a future Agent."""

    def __init__(self, code: ErrorCode, message: str) -> None:
        self.code = code
        self.safe_message = message
        super().__init__(message)


class CustomerNotFoundError(DomainError):
    def __init__(self, customer_id: str) -> None:
        super().__init__(ErrorCode.CUSTOMER_NOT_FOUND, f"Customer not found: {customer_id}")


class OrderNotFoundError(DomainError):
    def __init__(self, order_id: str) -> None:
        super().__init__(ErrorCode.ORDER_NOT_FOUND, f"Order not found: {order_id}")


class TicketNotFoundError(DomainError):
    def __init__(self, ticket_id: str) -> None:
        super().__init__(ErrorCode.TICKET_NOT_FOUND, f"Ticket not found: {ticket_id}")


class InvalidInputError(DomainError):
    def __init__(self, message: str) -> None:
        super().__init__(ErrorCode.INVALID_INPUT, message)


class DatabaseError(DomainError):
    def __init__(self) -> None:
        super().__init__(ErrorCode.DATABASE_ERROR, "The business database operation failed.")


class KnowledgeConfigMissingError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            ErrorCode.KNOWLEDGE_CONFIG_MISSING,
            "RAGFlow retrieval configuration is incomplete.",
        )


class KnowledgeServiceUnavailableError(DomainError):
    def __init__(self, message: str = "The knowledge retrieval service is unavailable.") -> None:
        super().__init__(ErrorCode.KNOWLEDGE_SERVICE_UNAVAILABLE, message)


class PolicyEvidenceNotFoundError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            ErrorCode.POLICY_EVIDENCE_NOT_FOUND,
            "No sufficiently relevant policy evidence was found.",
        )
