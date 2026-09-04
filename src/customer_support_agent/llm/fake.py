"""Deterministic scripted LLM replacement used by workflow tests."""

from __future__ import annotations

from collections import deque

from customer_support_agent.agent.schemas import (
    ActionPlan,
    AgentState,
    ResponseDraft,
    TicketClassification,
)
from customer_support_agent.core.errors import LLMStructuredOutputError


class ScriptedSupportLanguageModel:
    def __init__(
        self,
        classifications: list[TicketClassification | Exception],
        plans: list[ActionPlan | Exception],
        drafts: list[ResponseDraft | Exception],
    ) -> None:
        self.classifications = deque(classifications)
        self.plans = deque(plans)
        self.drafts = deque(drafts)

    @staticmethod
    def _next(queue, label: str):  # type: ignore[no-untyped-def]
        if not queue:
            raise LLMStructuredOutputError(f"No scripted {label} remains")
        value = queue.popleft()
        if isinstance(value, Exception):
            raise value
        return value

    def classify(
        self,
        user_message: str,
        known_customer_id: str | None,
        known_order_id: str | None,
        taxonomy: dict[str, list[str]],
    ) -> TicketClassification:
        del user_message, known_customer_id, known_order_id, taxonomy
        return self._next(self.classifications, "classification")

    def plan(self, state: AgentState) -> ActionPlan:
        del state
        return self._next(self.plans, "plan")

    def draft(self, state: AgentState) -> ResponseDraft:
        del state
        return self._next(self.drafts, "draft")
