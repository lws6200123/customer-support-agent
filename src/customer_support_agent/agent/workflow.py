"""Guarded Stage 5 LangGraph workflow for a single support Agent."""

from __future__ import annotations

import json
from datetime import datetime
from time import perf_counter
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from sqlalchemy import Engine

from customer_support_agent.agent.schemas import (
    ActionPlan,
    AgentAction,
    AgentRequest,
    AgentRunStatus,
    AgentState,
    Intent,
    PolicyEvidenceRecord,
    ResponseDraft,
    TicketClassification,
    ToolExecutionRecord,
)
from customer_support_agent.core.config import AppSettings
from customer_support_agent.core.errors import DomainError, ErrorCode, InvalidInputError
from customer_support_agent.core.schemas import Decision, RefundDecisionResult, TicketStatus, TicketUpdateInput
from customer_support_agent.db.engine import create_sqlite_engine
from customer_support_agent.llm.adapter import SupportLanguageModel
from customer_support_agent.services.knowledge_service import RAGFlowRetrievalClient
from customer_support_agent.services.rules import load_intent_taxonomy
from customer_support_agent.services.ticket_service import TicketService
from customer_support_agent.services.trace_service import AgentTraceService
from customer_support_agent.tools import create_business_tools, tools_by_name


POLICY_INTENTS = {
    Intent.RETURN_REFUND,
    Intent.DELIVERY,
    Intent.PRODUCT_AFTER_SALES,
    Intent.ACCOUNT,
    Intent.INVOICE,
}
ORDER_REQUIRED_INTENTS = {
    Intent.RETURN_REFUND,
    Intent.DELIVERY,
    Intent.PRODUCT_AFTER_SALES,
    Intent.INVOICE,
}

ACTION_TOOL_MAP: dict[AgentAction, str] = {
    AgentAction.LOOKUP_CUSTOMER: "lookup_customer",
    AgentAction.LOOKUP_ORDER: "lookup_order",
    AgentAction.LIST_CUSTOMER_ORDERS: "list_customer_orders",
    AgentAction.SEARCH_KNOWLEDGE: "search_knowledge",
    AgentAction.EVALUATE_REFUND: "evaluate_refund",
}

INTENT_ALLOWED_ACTIONS: dict[Intent, set[AgentAction]] = {
    Intent.RETURN_REFUND: set(AgentAction),
    Intent.DELIVERY: {
        AgentAction.LOOKUP_CUSTOMER,
        AgentAction.LOOKUP_ORDER,
        AgentAction.LIST_CUSTOMER_ORDERS,
        AgentAction.SEARCH_KNOWLEDGE,
    },
    Intent.PRODUCT_AFTER_SALES: {
        AgentAction.LOOKUP_CUSTOMER,
        AgentAction.LOOKUP_ORDER,
        AgentAction.LIST_CUSTOMER_ORDERS,
        AgentAction.SEARCH_KNOWLEDGE,
    },
    Intent.ACCOUNT: {AgentAction.LOOKUP_CUSTOMER, AgentAction.SEARCH_KNOWLEDGE},
    Intent.INVOICE: {
        AgentAction.LOOKUP_CUSTOMER,
        AgentAction.LOOKUP_ORDER,
        AgentAction.LIST_CUSTOMER_ORDERS,
        AgentAction.SEARCH_KNOWLEDGE,
    },
    Intent.OTHER: set(),
}


class SupportAgentWorkflow:
    """Stateful workflow with deterministic tool and resolution guardrails."""

    def __init__(
        self,
        llm: SupportLanguageModel,
        *,
        engine: Engine | None = None,
        settings: AppSettings | None = None,
        knowledge_client: RAGFlowRetrievalClient | None = None,
    ) -> None:
        self.settings = settings or AppSettings()
        self.engine = engine or create_sqlite_engine(self.settings.database_path)
        self.llm = llm
        self.taxonomy = load_intent_taxonomy()
        self.trace = AgentTraceService(self.engine)
        self.tickets = TicketService(self.engine, self.settings.simulation_now)
        self.tools = tools_by_name(
            create_business_tools(
                engine=self.engine,
                settings=self.settings,
                knowledge_client=knowledge_client,
            )
        )
        self.graph = self._build_graph()

    def _build_graph(self):  # type: ignore[no-untyped-def]
        builder = StateGraph(AgentState)
        builder.add_node("initialize_run", self.initialize_run)
        builder.add_node("classify_ticket", self.classify_ticket)
        builder.add_node("plan_actions", self.plan_actions)
        builder.add_node("validate_plan", self.validate_plan)
        builder.add_node("execute_action", self.execute_action)
        builder.add_node("evaluate_resolution", self.evaluate_resolution)
        builder.add_node("draft_response", self.draft_response)
        builder.add_node("persist_result", self.persist_result)
        builder.add_edge(START, "initialize_run")
        builder.add_edge("initialize_run", "classify_ticket")
        builder.add_edge("classify_ticket", "plan_actions")
        builder.add_edge("plan_actions", "validate_plan")
        builder.add_conditional_edges(
            "validate_plan",
            self._after_validation,
            {"execute": "execute_action", "resolve": "evaluate_resolution"},
        )
        builder.add_conditional_edges(
            "execute_action",
            self._after_execution,
            {"execute": "execute_action", "resolve": "evaluate_resolution"},
        )
        builder.add_edge("evaluate_resolution", "draft_response")
        builder.add_edge("draft_response", "persist_result")
        builder.add_edge("persist_result", END)
        return builder.compile()

    @staticmethod
    def _now() -> datetime:
        return datetime.now()

    def _record_node(
        self,
        state: AgentState,
        node_name: str,
        started: float,
        *,
        status: str = "SUCCESS",
        input_summary: str | None = None,
        output_summary: str | None = None,
        error_code: str | None = None,
    ) -> None:
        self.trace.record_step(
            state["run_id"],
            node_name=node_name,
            status=status,
            latency_ms=(perf_counter() - started) * 1000,
            input_summary=input_summary,
            output_summary=output_summary,
            error_code=error_code,
            created_at=self._now(),
        )

    def initialize_run(self, state: AgentState) -> AgentState:
        started = perf_counter()
        started_at = self._now()
        ticket_id = state.get("ticket_id")
        customer_id = state.get("customer_id")
        order_id = state.get("order_id")
        errors = list(state.get("error_codes", []))
        if ticket_id:
            try:
                ticket = self.tickets.get_ticket(ticket_id)
                if customer_id and ticket.customer_id != customer_id:
                    raise InvalidInputError("Ticket customer does not match the supplied customer.")
                if order_id and ticket.order_id != order_id:
                    raise InvalidInputError("Ticket order does not match the supplied order.")
                customer_id = customer_id or ticket.customer_id
                order_id = order_id or ticket.order_id
                if ticket.status in {TicketStatus.RESOLVED, TicketStatus.CLOSED}:
                    self.tickets.update_ticket(
                        TicketUpdateInput(ticket_id=ticket_id, status=TicketStatus.OPEN)
                    )
                    ticket = self.tickets.get_ticket(ticket_id)
                if ticket.status != TicketStatus.UNDER_REVIEW:
                    self.tickets.update_ticket(
                        TicketUpdateInput(ticket_id=ticket_id, status=TicketStatus.UNDER_REVIEW)
                    )
            except DomainError as exc:
                ticket_id = None
                errors.append(exc.code.value)
        run_id = self.trace.start_run(
            ticket_id=ticket_id,
            customer_id=customer_id,
            order_id=order_id,
            user_message=state["user_message"],
            started_at=started_at,
        )
        initialized: AgentState = {
            **state,
            "run_id": run_id,
            "run_status": AgentRunStatus.RUNNING,
            "ticket_id": ticket_id,
            "customer_id": customer_id,
            "order_id": order_id,
            "planned_actions": [],
            "completed_actions": [],
            "pending_actions": [],
            "tool_results": [],
            "policy_evidence": [],
            "refund_result": None,
            "decision": None,
            "missing_fields": [],
            "response_type": None,
            "final_response": None,
            "agent_summary": None,
            "error_codes": errors,
            "step_count": 0,
            "max_steps": self.settings.max_agent_steps,
            "tool_call_count": 0,
            "started_at": started_at,
            "completed_at": None,
            "total_latency_ms": None,
        }
        self._record_node(
            initialized,
            "initialize_run",
            started,
            output_summary="Agent run initialized; ticket loaded when supplied.",
            error_code=errors[-1] if errors else None,
        )
        return initialized

    def classify_ticket(self, state: AgentState) -> AgentState:
        started = perf_counter()
        errors = list(state["error_codes"])
        if errors and state.get("ticket_id") is None and ErrorCode.TICKET_NOT_FOUND.value in errors:
            result = {"decision": Decision.NEED_MORE_INFO, "missing_fields": ["valid_ticket_id"]}
            self._record_node(
                state,
                "classify_ticket",
                started,
                status="SKIPPED",
                output_summary="Classification skipped because the supplied ticket was not found.",
                error_code=ErrorCode.TICKET_NOT_FOUND.value,
            )
            return result  # type: ignore[return-value]
        try:
            classification = self.llm.classify(
                state["user_message"],
                state.get("customer_id"),
                state.get("order_id"),
                self.taxonomy,
            )
            allowed_sub_intents = self.taxonomy.get(classification.intent.value, [])
            if classification.sub_intent.value not in allowed_sub_intents:
                raise InvalidInputError("Classification sub_intent is outside the canonical taxonomy.")
            if state.get("customer_id") and classification.customer_id not in {
                None,
                state["customer_id"],
            }:
                raise InvalidInputError("LLM customer identifier conflicts with supplied context.")
            if state.get("order_id") and classification.order_id not in {None, state["order_id"]}:
                raise InvalidInputError("LLM order identifier conflicts with supplied context.")
            customer_id = state.get("customer_id") or classification.customer_id
            order_id = state.get("order_id") or classification.order_id
            self.trace.update_context(
                state["run_id"],
                ticket_id=state.get("ticket_id"),
                customer_id=customer_id,
                order_id=order_id,
                intent=classification.intent.value,
            )
            self._record_node(
                state,
                "classify_ticket",
                started,
                output_summary=(
                    f"intent={classification.intent.value}; "
                    f"sub_intent={classification.sub_intent.value}; priority={classification.priority.value}"
                ),
            )
            return {
                "classification": classification,
                "intent": classification.intent,
                "sub_intent": classification.sub_intent.value,
                "priority": classification.priority,
                "issue_summary": classification.issue_summary,
                "customer_id": customer_id,
                "order_id": order_id,
            }
        except DomainError as exc:
            errors.append(exc.code.value)
            self._record_node(
                state,
                "classify_ticket",
                started,
                status="FAILED",
                output_summary="Structured ticket classification failed safely.",
                error_code=exc.code.value,
            )
            return {
                "decision": Decision.ESCALATE_TO_HUMAN,
                "error_codes": errors,
            }

    def plan_actions(self, state: AgentState) -> AgentState:
        started = perf_counter()
        if state.get("decision") is not None or state.get("intent") is None:
            self._record_node(
                state,
                "plan_actions",
                started,
                status="SKIPPED",
                output_summary="Planning skipped because deterministic routing was already set.",
            )
            return {"planned_actions": []}
        errors = list(state["error_codes"])
        try:
            plan = self.llm.plan(state)
            self._record_node(
                state,
                "plan_actions",
                started,
                output_summary=f"LLM proposed {len(plan.actions)} allowlisted action values.",
            )
            return {"planned_actions": plan.actions}
        except DomainError as exc:
            errors.append(exc.code.value)
            self._record_node(
                state,
                "plan_actions",
                started,
                status="FAILED",
                output_summary="Structured action planning failed safely.",
                error_code=exc.code.value,
            )
            return {
                "planned_actions": [],
                "decision": Decision.ESCALATE_TO_HUMAN,
                "error_codes": errors,
            }

    def validate_plan(self, state: AgentState) -> AgentState:
        started = perf_counter()
        if state.get("decision") is not None or state.get("intent") is None:
            self._record_node(
                state,
                "validate_plan",
                started,
                status="SKIPPED",
                output_summary="No executable plan was accepted.",
            )
            return {"pending_actions": []}
        intent = state["intent"]
        allowed = INTENT_ALLOWED_ACTIONS[intent]
        accepted: list[AgentAction] = []

        def add(action: AgentAction) -> None:
            if action in allowed and action not in accepted:
                accepted.append(action)

        if state.get("customer_id"):
            add(AgentAction.LOOKUP_CUSTOMER)
        if state.get("order_id"):
            add(AgentAction.LOOKUP_ORDER)
        elif state.get("customer_id") and intent in ORDER_REQUIRED_INTENTS:
            add(AgentAction.LIST_CUSTOMER_ORDERS)
        if intent in POLICY_INTENTS:
            add(AgentAction.SEARCH_KNOWLEDGE)
        if intent == Intent.RETURN_REFUND and state.get("order_id"):
            add(AgentAction.EVALUATE_REFUND)
        for action in state.get("planned_actions", []):
            if action == AgentAction.EVALUATE_REFUND and not state.get("order_id"):
                continue
            if action == AgentAction.LIST_CUSTOMER_ORDERS and not state.get("customer_id"):
                continue
            if action == AgentAction.LIST_CUSTOMER_ORDERS and state.get("order_id"):
                continue
            if action == AgentAction.LOOKUP_CUSTOMER and not state.get("customer_id"):
                continue
            if action == AgentAction.LOOKUP_ORDER and not state.get("order_id"):
                continue
            add(action)
        errors = list(state["error_codes"])
        if len(accepted) > state["max_steps"]:
            accepted = accepted[: state["max_steps"]]
            errors.append(ErrorCode.AGENT_STEP_LIMIT_REACHED.value)
        self._record_node(
            state,
            "validate_plan",
            started,
            output_summary="validated_actions=" + ",".join(action.value for action in accepted),
            error_code=(
                ErrorCode.AGENT_STEP_LIMIT_REACHED.value
                if ErrorCode.AGENT_STEP_LIMIT_REACHED.value in errors
                else None
            ),
        )
        return {
            "planned_actions": accepted,
            "pending_actions": accepted,
            "error_codes": errors,
        }

    @staticmethod
    def _after_validation(state: AgentState) -> Literal["execute", "resolve"]:
        return "execute" if state.get("pending_actions") else "resolve"

    @staticmethod
    def _after_execution(state: AgentState) -> Literal["execute", "resolve"]:
        return "execute" if state.get("pending_actions") else "resolve"

    def _tool_input(self, action: AgentAction, state: AgentState) -> dict[str, Any]:
        if action == AgentAction.LOOKUP_CUSTOMER:
            return {"customer_id": state.get("customer_id")}
        if action == AgentAction.LOOKUP_ORDER:
            return {"order_id": state.get("order_id")}
        if action == AgentAction.LIST_CUSTOMER_ORDERS:
            return {"customer_id": state.get("customer_id")}
        if action == AgentAction.SEARCH_KNOWLEDGE:
            return {
                "query": (
                    f"{state.get('intent', Intent.OTHER).value} "
                    f"{state.get('sub_intent', '')}: {state.get('issue_summary', '')}"
                )
            }
        classification = state["classification"]
        return {
            "order_id": state.get("order_id"),
            "reason_code": (
                classification.reason_code.value if classification.reason_code else None
            ),
            "requested_amount": classification.requested_amount,
            "issue_description": classification.issue_summary,
            "product_condition_ok": classification.product_condition_ok,
            "defect_confirmed": classification.defect_confirmed,
            "evidence_confirmed": classification.evidence_confirmed,
        }

    @staticmethod
    def _decode_envelope(value: Any) -> dict[str, Any]:
        if isinstance(value, str):
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _tool_summary(action: AgentAction, envelope: dict[str, Any]) -> str:
        if not envelope.get("ok"):
            return f"{action.value} failed with {envelope.get('error_code') or 'UNKNOWN_ERROR'}."
        data = envelope.get("data")
        if action == AgentAction.LOOKUP_ORDER and isinstance(data, dict):
            return (
                f"Order retrieved: status={data.get('status')}; "
                f"items={len(data.get('items', []))}; payments={len(data.get('payments', []))}."
            )
        if action == AgentAction.LOOKUP_CUSTOMER:
            return "Customer context retrieved."
        if action == AgentAction.LIST_CUSTOMER_ORDERS and isinstance(data, list):
            return f"Customer order summaries retrieved: count={len(data)}."
        if action == AgentAction.SEARCH_KNOWLEDGE and isinstance(data, dict):
            ids = [item.get("document_id") for item in data.get("results", [])[:3]]
            return f"Policy evidence retrieved: top_documents={ids}."
        if action == AgentAction.EVALUATE_REFUND and isinstance(data, dict):
            return (
                f"Refund evaluated: decision={data.get('decision')}; "
                f"eligible={data.get('eligible')}; reason_codes={data.get('reason_codes')}."
            )
        return f"{action.value} completed."

    def execute_action(self, state: AgentState) -> AgentState:
        if not state.get("pending_actions"):
            return {}
        if state["step_count"] >= state["max_steps"]:
            errors = list(state["error_codes"])
            errors.append(ErrorCode.AGENT_STEP_LIMIT_REACHED.value)
            started = perf_counter()
            self._record_node(
                state,
                "execute_action",
                started,
                status="FAILED",
                output_summary="Agent action loop stopped at the configured bound.",
                error_code=ErrorCode.AGENT_STEP_LIMIT_REACHED.value,
            )
            return {
                "pending_actions": [],
                "decision": Decision.ESCALATE_TO_HUMAN,
                "error_codes": errors,
            }
        action = state["pending_actions"][0]
        remaining = state["pending_actions"][1:]
        tool_name = ACTION_TOOL_MAP[action]
        tool_input = self._tool_input(action, state)
        started = perf_counter()
        try:
            envelope = self._decode_envelope(self.tools[tool_name].invoke(tool_input))
        except Exception:
            envelope = {
                "ok": False,
                "data": None,
                "error_code": ErrorCode.DATABASE_ERROR.value,
                "message": "Tool execution failed safely.",
            }
        latency_ms = (perf_counter() - started) * 1000
        error_code = envelope.get("error_code")
        summary = self._tool_summary(action, envelope)
        record = ToolExecutionRecord(
            action=action,
            tool_name=tool_name,
            ok=bool(envelope.get("ok")),
            error_code=str(error_code) if error_code else None,
            summary=summary,
            latency_ms=latency_ms,
        )
        self.trace.record_step(
            state["run_id"],
            node_name="execute_action",
            action=action.value,
            tool_name=tool_name,
            status="SUCCESS" if record.ok else "FAILED",
            latency_ms=latency_ms,
            input_summary="Validated structured input; identifiers omitted from trace summary.",
            output_summary=summary,
            error_code=record.error_code,
            created_at=self._now(),
        )
        updates: AgentState = {
            "pending_actions": remaining,
            "completed_actions": [*state["completed_actions"], action],
            "tool_results": [*state["tool_results"], record],
            "step_count": state["step_count"] + 1,
            "tool_call_count": state["tool_call_count"] + 1,
        }
        errors = list(state["error_codes"])
        if record.error_code:
            errors.append(record.error_code)
            updates["error_codes"] = errors
        data = envelope.get("data")
        if record.ok and action == AgentAction.LOOKUP_ORDER and isinstance(data, dict):
            updates["customer_id"] = state.get("customer_id") or data.get("customer_id")
        elif record.ok and action == AgentAction.SEARCH_KNOWLEDGE and isinstance(data, dict):
            updates["policy_evidence"] = [
                PolicyEvidenceRecord.model_validate(item) for item in data.get("results", [])
            ]
        elif record.ok and action == AgentAction.EVALUATE_REFUND and isinstance(data, dict):
            updates["refund_result"] = RefundDecisionResult.model_validate(data)
        return updates

    def evaluate_resolution(self, state: AgentState) -> AgentState:
        started = perf_counter()
        decision = state.get("decision")
        missing = list(state.get("missing_fields", []))
        errors = set(state["error_codes"])
        if decision is None:
            if ErrorCode.AGENT_STEP_LIMIT_REACHED.value in errors:
                decision = Decision.ESCALATE_TO_HUMAN
            elif errors & {
                ErrorCode.KNOWLEDGE_SERVICE_UNAVAILABLE.value,
                ErrorCode.KNOWLEDGE_CONFIG_MISSING.value,
                ErrorCode.POLICY_EVIDENCE_NOT_FOUND.value,
                ErrorCode.DATABASE_ERROR.value,
                ErrorCode.LLM_STRUCTURED_OUTPUT_FAILED.value,
                ErrorCode.LLM_UNAVAILABLE.value,
            }:
                decision = Decision.ESCALATE_TO_HUMAN
            elif errors & {
                ErrorCode.CUSTOMER_NOT_FOUND.value,
                ErrorCode.ORDER_NOT_FOUND.value,
                ErrorCode.INVALID_INPUT.value,
                ErrorCode.TICKET_NOT_FOUND.value,
            }:
                decision = Decision.NEED_MORE_INFO
            elif state.get("intent") == Intent.RETURN_REFUND:
                refund_result = state.get("refund_result")
                if refund_result is not None:
                    decision = refund_result.decision
                    missing = refund_result.missing_fields
                elif not state.get("order_id"):
                    decision = Decision.NEED_MORE_INFO
                    missing.append("order_id")
                else:
                    decision = Decision.ESCALATE_TO_HUMAN
            elif state.get("intent") in ORDER_REQUIRED_INTENTS and not state.get("order_id"):
                decision = Decision.NEED_MORE_INFO
                missing.append("order_id")
            elif state.get("intent") == Intent.ACCOUNT and not state.get("customer_id"):
                decision = Decision.NEED_MORE_INFO
                missing.append("customer_id")
            elif state.get("intent") in POLICY_INTENTS and not state.get("policy_evidence"):
                decision = Decision.ESCALATE_TO_HUMAN
            else:
                decision = Decision.AUTO_RESOLVE
        missing = sorted(set(missing))
        self._record_node(
            state,
            "evaluate_resolution",
            started,
            output_summary=f"deterministic_decision={decision.value}; missing_fields={missing}",
        )
        return {"decision": decision, "response_type": decision, "missing_fields": missing}

    @staticmethod
    def _safe_fallback(state: AgentState) -> ResponseDraft:
        decision = state["decision"]
        if decision == Decision.NEED_MORE_INFO:
            fields = ", ".join(state.get("missing_fields", [])) or "additional order details"
            response = f"To continue, please provide the following information: {fields}."
        elif decision == Decision.ESCALATE_TO_HUMAN:
            response = "Your request requires further manual review. A support specialist should review the available details before any action is taken."
        elif state.get("intent") == Intent.RETURN_REFUND:
            response = "The request meets the current DemoShop decision criteria. This is a preliminary decision only; no refund has been executed."
        else:
            response = "Based on the available verified information, the request can follow the documented support guidance. No account or payment action has been executed."
        summary = (
            f"intent={state.get('intent')}; decision={decision}; "
            f"tools={[action.value for action in state.get('completed_actions', [])]}; "
            f"errors={state.get('error_codes', [])}"
        )
        return ResponseDraft(customer_response=response, agent_summary=summary)

    @staticmethod
    def _unsafe_customer_text(text: str, decision: Decision) -> bool:
        lowered = text.casefold()
        internal_terms = ("risk_flag", "fraud flag", "risk user", "风险用户")
        completion_claims = (
            "refund has been completed",
            "refund is complete",
            "退款已经完成",
            "退款已完成",
        )
        return any(term in lowered for term in internal_terms) or (
            decision == Decision.AUTO_RESOLVE
            and any(term in lowered for term in completion_claims)
        )

    def draft_response(self, state: AgentState) -> AgentState:
        started = perf_counter()
        errors = list(state["error_codes"])
        try:
            draft = self.llm.draft(state)
            if self._unsafe_customer_text(draft.customer_response, state["decision"]):
                raise InvalidInputError("Draft violated response safety rules.")
            status = "SUCCESS"
            error_code = None
        except Exception as exc:
            draft = self._safe_fallback(state)
            status = "FALLBACK"
            error_code = exc.code.value if isinstance(exc, DomainError) else ErrorCode.LLM_UNAVAILABLE.value
            errors.append(error_code)
        self._record_node(
            state,
            "draft_response",
            started,
            status=status,
            output_summary="Customer response and internal summary generated without persisted prompt content.",
            error_code=error_code,
        )
        return {
            "final_response": draft.customer_response,
            "agent_summary": draft.agent_summary,
            "error_codes": errors,
        }

    def _update_ticket_lifecycle(self, state: AgentState) -> None:
        ticket_id = state.get("ticket_id")
        if not ticket_id:
            return
        decision = state["decision"]
        status = {
            Decision.AUTO_RESOLVE: TicketStatus.RESOLVED,
            Decision.NEED_MORE_INFO: TicketStatus.AWAITING_CUSTOMER,
            Decision.ESCALATE_TO_HUMAN: TicketStatus.UNDER_REVIEW,
        }[decision]
        current = self.tickets.get_ticket(ticket_id)
        if current.status != status:
            self.tickets.update_ticket(TicketUpdateInput(ticket_id=ticket_id, status=status))
        self.tickets.update_ticket(
            TicketUpdateInput(
                ticket_id=ticket_id,
                decision=decision,
                resolution=(state.get("final_response") if decision == Decision.AUTO_RESOLVE else None),
                notes=(
                    "Agent requested additional customer information."
                    if decision == Decision.NEED_MORE_INFO
                    else "Agent routed request for manual review."
                    if decision == Decision.ESCALATE_TO_HUMAN
                    else None
                ),
            )
        )

    def persist_result(self, state: AgentState) -> AgentState:
        started = perf_counter()
        errors = list(state["error_codes"])
        try:
            self._update_ticket_lifecycle(state)
            run_status = {
                Decision.AUTO_RESOLVE: AgentRunStatus.COMPLETED,
                Decision.NEED_MORE_INFO: AgentRunStatus.NEED_MORE_INFO,
                Decision.ESCALATE_TO_HUMAN: AgentRunStatus.ESCALATED,
            }[state["decision"]]
            status = "SUCCESS"
            error_code = None
        except DomainError as exc:
            run_status = AgentRunStatus.FAILED
            status = "FAILED"
            error_code = exc.code.value
            errors.append(error_code)
        self._record_node(
            state,
            "persist_result",
            started,
            status=status,
            output_summary=f"run_status={run_status.value}; ticket lifecycle persisted when available.",
            error_code=error_code,
        )
        completed_at = self._now()
        total_latency_ms = (completed_at - state["started_at"]).total_seconds() * 1000
        self.trace.finish_run(
            state["run_id"],
            status=run_status,
            decision=state["decision"],
            completed_at=completed_at,
            total_latency_ms=total_latency_ms,
            tool_call_count=state["tool_call_count"],
            error_codes=errors,
            final_response=state.get("final_response"),
            agent_summary=state.get("agent_summary"),
        )
        return {
            "completed_at": completed_at,
            "total_latency_ms": total_latency_ms,
            "error_codes": errors,
            "run_status": run_status,
        }

    def run(self, request: AgentRequest | dict[str, Any]) -> AgentState:
        initial = self._initial_state(request)
        try:
            return self.graph.invoke(initial)
        except Exception:
            completed_at = self._now()
            return {
                **initial,
                "run_status": AgentRunStatus.FAILED,
                "decision": Decision.ESCALATE_TO_HUMAN,
                "response_type": Decision.ESCALATE_TO_HUMAN,
                "final_response": (
                    "We could not safely complete this request because of a system problem. "
                    "Please ask a support specialist to review it."
                ),
                "agent_summary": "Workflow failed safely before normal completion.",
                "error_codes": [ErrorCode.DATABASE_ERROR.value],
                "completed_at": completed_at,
                "fatal_error": True,
            }

    @staticmethod
    def _initial_state(request: AgentRequest | dict[str, Any]) -> AgentState:
        validated = request if isinstance(request, AgentRequest) else AgentRequest.model_validate(request)
        initial: AgentState = {
            "ticket_id": validated.ticket_id,
            "user_message": validated.user_message,
            "customer_id": validated.customer_id,
            "order_id": validated.order_id,
            "error_codes": [],
        }
        return initial

    def stream_updates(
        self, request: AgentRequest | dict[str, Any]
    ):  # type: ignore[no-untyped-def]
        """Yield node name and accumulated state from the same compiled graph as ``run``."""
        accumulated = self._initial_state(request)
        for update in self.graph.stream(accumulated, stream_mode="updates"):
            for node_name, values in update.items():
                if isinstance(values, dict):
                    accumulated.update(values)
                yield node_name, dict(accumulated)
