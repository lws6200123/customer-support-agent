"""OpenAI-compatible DeepSeek adapter with bounded structured-output retries."""

from __future__ import annotations

import asyncio
import json
from typing import Protocol, TypeVar

import httpx
from openai import APIConnectionError, APITimeoutError
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from customer_support_agent.agent.schemas import (
    ActionPlan,
    AgentState,
    ResponseDraft,
    TicketClassification,
)
from customer_support_agent.core.config import AppSettings
from customer_support_agent.core.errors import (
    LLMConfigMissingError,
    LLMStructuredOutputError,
    LLMUnavailableError,
)


class SupportLanguageModel(Protocol):
    def classify(
        self,
        user_message: str,
        known_customer_id: str | None,
        known_order_id: str | None,
        taxonomy: dict[str, list[str]],
    ) -> TicketClassification: ...

    def plan(self, state: AgentState) -> ActionPlan: ...

    def draft(self, state: AgentState) -> ResponseDraft: ...


SchemaT = TypeVar("SchemaT", bound=BaseModel)


class DeepSeekChatModel:
    """DeepSeek via a replaceable OpenAI-compatible LangChain chat adapter."""

    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or AppSettings()
        if not self.settings.deepseek_configured:
            raise LLMConfigMissingError()
        self.http_client = httpx.Client(
            timeout=self.settings.deepseek_timeout_seconds,
            trust_env=False,
        )
        self.http_async_client = httpx.AsyncClient(
            timeout=self.settings.deepseek_timeout_seconds,
            trust_env=False,
        )
        self.chat_model = ChatOpenAI(
            model=self.settings.deepseek_model,
            base_url=self.settings.deepseek_base_url,
            api_key=self.settings.deepseek_api_key,
            timeout=self.settings.deepseek_timeout_seconds,
            max_retries=self.settings.deepseek_max_retries,
            temperature=0,
            http_client=self.http_client,
            http_async_client=self.http_async_client,
        )

    def _structured(
        self,
        schema: type[SchemaT],
        system_prompt: str,
        payload: dict[str, object],
    ) -> SchemaT:
        model = self.chat_model.with_structured_output(schema, method="json_mode")
        schema_text = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        messages = [
            SystemMessage(
                content=(
                    f"{system_prompt}\nReturn only JSON matching this schema: {schema_text}"
                )
            ),
            HumanMessage(content=json.dumps(payload, ensure_ascii=False, default=str)),
        ]
        last_error: Exception | None = None
        for _ in range(self.settings.llm_structured_output_attempts):
            try:
                result = model.invoke(messages)
                return schema.model_validate(result)
            except Exception as exc:  # External adapter errors are normalized at the boundary.
                last_error = exc
        if isinstance(last_error, (APIConnectionError, APITimeoutError)):
            raise LLMUnavailableError() from last_error
        raise LLMStructuredOutputError() from last_error

    def close(self) -> None:
        """Release explicitly managed sync/async HTTP clients in sync runtimes."""
        self.http_client.close()
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self.http_async_client.aclose())

    def classify(
        self,
        user_message: str,
        known_customer_id: str | None,
        known_order_id: str | None,
        taxonomy: dict[str, list[str]],
    ) -> TicketClassification:
        return self._structured(
            TicketClassification,
            (
                "Classify and extract facts only. Use the supplied taxonomy exactly. Do not "
                "invent customer_id or order_id, decide refund eligibility, modify data, or "
                "force an unclear request into a non-OTHER intent. Preserve known identifiers. "
                "Set human_review_requested only when the customer explicitly asks for a human "
                "review. Mark explicit legal/regulatory complaints and personal-safety-sensitive "
                "requests with their dedicated booleans."
            ),
            {
                "user_message": user_message,
                "known_customer_id": known_customer_id,
                "known_order_id": known_order_id,
                "taxonomy": taxonomy,
            },
        )

    def plan(self, state: AgentState) -> ActionPlan:
        return self._structured(
            ActionPlan,
            (
                "Plan only from the AgentAction enum. Never create SQL, database mutation, "
                "money approval, ticket mutation, or invented tool names. The deterministic "
                "graph will validate and may replace this plan."
            ),
            {
                "intent": state.get("intent"),
                "sub_intent": state.get("sub_intent"),
                "customer_id_known": bool(state.get("customer_id")),
                "order_id_known": bool(state.get("order_id")),
                "issue_summary": state.get("issue_summary"),
                "completed_actions": state.get("completed_actions", []),
                "tool_summaries": [item.summary for item in state.get("tool_results", [])],
            },
        )

    def draft(self, state: AgentState) -> ResponseDraft:
        evidence = [
            {
                "document_id": item.document_id,
                "content": item.content[:1200],
                "source_type": item.source_type,
            }
            for item in state.get("policy_evidence", [])[:3]
        ]
        refund = state.get("refund_result")
        return self._structured(
            ResponseDraft,
            (
                "Write a concise customer response and an internal agent summary. Use only the "
                "provided facts, tool results, policy evidence, and deterministic decision. Do "
                "not invent order facts or refund receipt status, promise an unexecuted action, "
                "or expose risk/fraud flags. AUTO_RESOLVE is a demo candidate and never means "
                "money was refunded. For escalation use neutral customer-facing language."
            ),
            {
                "user_message": state["user_message"],
                "intent": state.get("intent"),
                "issue_summary": state.get("issue_summary"),
                "decision": state.get("decision"),
                "missing_fields": state.get("missing_fields", []),
                "tool_summaries": [item.summary for item in state.get("tool_results", [])],
                "policy_evidence": evidence,
                "refund_result": refund.model_dump(mode="json") if refund else None,
            },
        )
