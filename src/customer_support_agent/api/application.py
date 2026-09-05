"""Application services that keep HTTP routers free of SQL and Agent logic."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime

from sqlalchemy import Engine, and_, desc, func, insert, select

from customer_support_agent.agent.schemas import AgentRequest, AgentState, Intent
from customer_support_agent.agent.workflow import SupportAgentWorkflow
from customer_support_agent.api.errors import ApiConflictError
from customer_support_agent.api.schemas import (
    AgentRunRequest,
    AgentRunResult,
    AgentRunSummary,
    CountByName,
    CustomerSummary,
    DashboardSummary,
    HumanReviewAction,
    HumanReviewItem,
    HumanReviewPage,
    HumanReviewRequest,
    HumanReviewResult,
    OrderSummary,
    SseEventPayload,
    TicketCreateRequest,
    TicketCreated,
    TicketDetail,
    TicketListItem,
    TicketPage,
    TraceStep,
    TraceSteps,
)
from customer_support_agent.core.config import AppSettings
from customer_support_agent.core.errors import DatabaseError, InvalidInputError
from customer_support_agent.core.schemas import Decision, TicketCreateInput, TicketStatus, TicketUpdateInput
from customer_support_agent.db.models import AgentRun, Customer, HumanReview, Order, Payment, Ticket
from customer_support_agent.services.ticket_service import TicketService
from customer_support_agent.services.trace_service import AgentTraceService


WorkflowFactory = Callable[[], SupportAgentWorkflow]


class TicketApplicationService:
    def __init__(self, engine: Engine, settings: AppSettings) -> None:
        self.engine = engine
        self.settings = settings
        self.tickets = TicketService(engine, settings.simulation_now)

    @staticmethod
    def _ticket(row) -> TicketListItem:  # type: ignore[no-untyped-def]
        values = dict(row)
        return TicketListItem.model_validate(
            {name: values[name] for name in TicketListItem.model_fields}
        )

    def list_tickets(
        self,
        *,
        page: int,
        page_size: int,
        status: TicketStatus | None,
        decision: Decision | None,
        intent: Intent | None,
    ) -> TicketPage:
        filters = []
        if status is not None:
            filters.append(Ticket.status == status.value)
        if decision is not None:
            filters.append(Ticket.decision == decision.value)
        if intent is not None:
            filters.append(
                select(AgentRun.agent_run_id)
                .where(
                    AgentRun.ticket_id == Ticket.ticket_id,
                    AgentRun.intent == intent.value,
                )
                .exists()
            )
        where = and_(*filters) if filters else True
        with self.engine.connect() as connection:
            total = int(connection.scalar(select(func.count()).select_from(Ticket).where(where)) or 0)
            rows = connection.execute(
                select(Ticket.__table__)
                .where(where)
                .order_by(Ticket.created_at.desc(), Ticket.ticket_id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).mappings().all()
        return TicketPage(
            items=[self._ticket(row) for row in rows],
            page=page,
            page_size=page_size,
            total=total,
        )

    def create_ticket(self, request: TicketCreateRequest) -> TicketCreated:
        if not request.customer_id or not request.order_id:
            raise InvalidInputError(
                "customer_id and order_id are required to persist a linked demo ticket."
            )
        ticket = self.tickets.create_ticket(
            TicketCreateInput(
                customer_id=request.customer_id,
                order_id=request.order_id,
                category=Intent.OTHER.value,
                priority=request.priority,
                subject=request.message[:255],
                notes=request.message,
            )
        )
        return TicketCreated(ticket_id=ticket.ticket_id, status=ticket.status)

    def _customer_summary(self, customer_id: str) -> CustomerSummary | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(Customer.customer_id, Customer.display_name, Customer.city, Customer.state)
                .where(Customer.customer_id == customer_id)
            ).mappings().first()
        return CustomerSummary.model_validate(dict(row)) if row else None

    def _order_summary(self, order_id: str) -> OrderSummary | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(
                    Order.order_id,
                    Order.status,
                    Order.purchase_at,
                    Order.delivered_at,
                    Order.estimated_delivery_at,
                    func.coalesce(func.sum(Payment.payment_value), 0.0).label("payment_total"),
                )
                .outerjoin(Payment, Payment.order_id == Order.order_id)
                .where(Order.order_id == order_id)
                .group_by(Order.order_id)
            ).mappings().first()
        if not row:
            return None
        values = dict(row)
        values["payment_total"] = round(float(values["payment_total"]), 2)
        values["currency"] = "BRL"
        return OrderSummary.model_validate(values)

    @staticmethod
    def _run_summary(row) -> AgentRunSummary:  # type: ignore[no-untyped-def]
        values = dict(row)
        values["run_id"] = values.pop("agent_run_id")
        values["response"] = values.pop("final_response")
        values["latency_ms"] = values.pop("total_latency_ms")
        values.pop("customer_id", None)
        values.pop("order_id", None)
        values.pop("user_message", None)
        values.pop("error_summary", None)
        return AgentRunSummary.model_validate(values)

    def get_ticket_detail(self, ticket_id: str) -> TicketDetail:
        ticket = self.tickets.get_ticket(ticket_id)
        with self.engine.connect() as connection:
            run = connection.execute(
                select(AgentRun.__table__)
                .where(AgentRun.ticket_id == ticket_id)
                .order_by(AgentRun.agent_run_id.desc())
                .limit(1)
            ).mappings().first()
        return TicketDetail(
            ticket=self._ticket(ticket.model_dump()),
            customer=self._customer_summary(ticket.customer_id),
            order=self._order_summary(ticket.order_id),
            latest_agent_run=self._run_summary(run) if run else None,
        )


class AgentApplicationService:
    def __init__(self, engine: Engine, settings: AppSettings, workflow_factory: WorkflowFactory) -> None:
        self.engine = engine
        self.settings = settings
        self.workflow_factory = workflow_factory
        self.tickets = TicketApplicationService(engine, settings)
        self.trace = AgentTraceService(engine)

    def _prepare(self, request: AgentRunRequest) -> AgentRequest:
        ticket_id = request.ticket_id
        if ticket_id:
            self.tickets.tickets.get_ticket(ticket_id)
        elif request.customer_id and request.order_id:
            created = self.tickets.create_ticket(
                TicketCreateRequest(
                    message=request.message,
                    customer_id=request.customer_id,
                    order_id=request.order_id,
                )
            )
            ticket_id = created.ticket_id
        return AgentRequest(
            user_message=request.message,
            customer_id=request.customer_id,
            order_id=request.order_id,
            ticket_id=ticket_id,
        )

    @staticmethod
    def _close(workflow: SupportAgentWorkflow) -> None:
        closer = getattr(workflow.llm, "close", None)
        if callable(closer):
            closer()

    def run(self, request: AgentRunRequest) -> AgentRunResult:
        prepared = self._prepare(request)
        workflow = self.workflow_factory()
        try:
            state = workflow.run(prepared)
        finally:
            self._close(workflow)
        return self._result(state)

    def _result(self, state: AgentState) -> AgentRunResult:
        run_id = state.get("run_id")
        if run_id is None:
            raise DatabaseError()
        ticket_status = None
        if state.get("ticket_id"):
            ticket_status = self.tickets.tickets.get_ticket(state["ticket_id"]).status
        return AgentRunResult(
            run_id=run_id,
            ticket_id=state.get("ticket_id"),
            intent=state.get("intent"),
            decision=state.get("decision") or Decision.ESCALATE_TO_HUMAN,
            ticket_status=ticket_status,
            response=state.get("final_response") or "The request could not be completed safely.",
            agent_summary=state.get("agent_summary") or "Workflow ended without a summary.",
            tool_call_count=state.get("tool_call_count", 0),
            latency_ms=state.get("total_latency_ms"),
        )

    def stream(self, request: AgentRunRequest) -> Iterator[SseEventPayload]:
        workflow: SupportAgentWorkflow | None = None
        try:
            prepared = self._prepare(request)
            workflow = self.workflow_factory()
            for node, state in workflow.stream_updates(prepared):
                timestamp = datetime.now()
                common = {
                    "timestamp": timestamp,
                    "run_id": state.get("run_id"),
                    "ticket_id": state.get("ticket_id"),
                }
                if node == "initialize_run":
                    yield SseEventPayload(event="run_started", detail="Agent run started.", **common)
                elif node == "classify_ticket":
                    yield SseEventPayload(
                        event="classification",
                        intent=state.get("intent"),
                        detail="Ticket classification completed.",
                        **common,
                    )
                elif node == "execute_action" and state.get("tool_results"):
                    tool = state["tool_results"][-1]
                    yield SseEventPayload(
                        event="tool_started", tool=tool.tool_name, detail="Validated tool started.", **common
                    )
                    yield SseEventPayload(
                        event="tool_completed",
                        tool=tool.tool_name,
                        tool_ok=tool.ok,
                        detail=tool.summary,
                        **common,
                    )
                elif node == "evaluate_resolution":
                    yield SseEventPayload(
                        event="decision", decision=state.get("decision"), detail="Decision computed.", **common
                    )
                elif node == "draft_response":
                    yield SseEventPayload(
                        event="final_response", response=state.get("final_response"), **common
                    )
                elif node == "persist_result":
                    yield SseEventPayload(
                        event="run_completed",
                        decision=state.get("decision"),
                        detail="Agent run persisted.",
                        **common,
                    )
        except Exception:
            yield SseEventPayload(
                timestamp=datetime.now(),
                event="error",
                detail="The Agent stream terminated safely.",
            )
        finally:
            if workflow is not None:
                self._close(workflow)

    def get_run(self, run_id: int) -> AgentRunSummary:
        trace = self.trace.get_trace(run_id)
        return AgentRunSummary(
            run_id=trace.agent_run_id,
            ticket_id=trace.ticket_id,
            intent=Intent(trace.intent) if trace.intent else None,
            decision=trace.decision,
            status=trace.status,
            response=trace.final_response,
            agent_summary=trace.agent_summary,
            tool_call_count=trace.tool_call_count,
            latency_ms=trace.total_latency_ms,
            started_at=trace.started_at,
            completed_at=trace.completed_at,
        )

    def get_steps(self, run_id: int) -> TraceSteps:
        trace = self.trace.get_trace(run_id)
        return TraceSteps(
            run_id=run_id,
            items=[
                TraceStep(
                    sequence=item.step_sequence,
                    node=item.node_name,
                    action=item.action,
                    tool=item.tool_name,
                    status=item.status,
                    latency_ms=item.latency_ms,
                    input_summary=item.input_summary,
                    output_summary=item.output_summary,
                    error_code=item.error_code,
                    created_at=item.created_at,
                )
                for item in trace.steps
            ],
        )


class HumanReviewApplicationService:
    def __init__(self, engine: Engine, settings: AppSettings) -> None:
        self.engine = engine
        self.settings = settings
        self.tickets = TicketApplicationService(engine, settings)

    def list_reviews(self, *, page: int, page_size: int) -> HumanReviewPage:
        latest = (
            select(AgentRun.ticket_id, func.max(AgentRun.agent_run_id).label("run_id"))
            .where(AgentRun.ticket_id.is_not(None))
            .group_by(AgentRun.ticket_id)
            .subquery()
        )
        base = (
            select(Ticket.__table__, AgentRun.__table__)
            .join(latest, latest.c.ticket_id == Ticket.ticket_id)
            .join(AgentRun, AgentRun.agent_run_id == latest.c.run_id)
            .where(
                Ticket.status == TicketStatus.UNDER_REVIEW.value,
                AgentRun.decision == Decision.ESCALATE_TO_HUMAN.value,
            )
        )
        with self.engine.connect() as connection:
            total = int(connection.scalar(select(func.count()).select_from(base.subquery())) or 0)
            rows = connection.execute(
                base.order_by(AgentRun.started_at.desc()).offset((page - 1) * page_size).limit(page_size)
            ).mappings().all()
        items = []
        for row in rows:
            errors = str(row.get("error_summary") or "")
            items.append(
                HumanReviewItem(
                    ticket_id=row["ticket_id"],
                    run_id=row["agent_run_id"],
                    intent=Intent(row["intent"]) if row.get("intent") else None,
                    priority=row["priority"],
                    customer=self.tickets._customer_summary(row["customer_id"]),
                    order=self.tickets._order_summary(row["order_id"]),
                    agent_summary=row.get("agent_summary"),
                    reason_codes=[part for part in errors.split(",") if part],
                    created_at=row["started_at"],
                )
            )
        return HumanReviewPage(items=items, page=page, page_size=page_size, total=total)

    def review(self, ticket_id: str, request: HumanReviewRequest) -> HumanReviewResult:
        ticket = self.tickets.tickets.get_ticket(ticket_id)
        if ticket.status != TicketStatus.UNDER_REVIEW or ticket.decision != Decision.ESCALATE_TO_HUMAN:
            raise ApiConflictError("Only canonically escalated tickets can receive a review action.")
        status = {
            HumanReviewAction.RESOLVE: TicketStatus.RESOLVED,
            HumanReviewAction.REQUEST_MORE_INFO: TicketStatus.AWAITING_CUSTOMER,
            HumanReviewAction.KEEP_ESCALATED: TicketStatus.UNDER_REVIEW,
        }[request.action]
        note = request.review_note or {
            HumanReviewAction.RESOLVE: "Reviewer resolved the demo ticket; no payment action was executed.",
            HumanReviewAction.REQUEST_MORE_INFO: "Reviewer requested additional customer information.",
            HumanReviewAction.KEEP_ESCALATED: "Reviewer kept the ticket in manual review.",
        }[request.action]
        if status != ticket.status:
            self.tickets.tickets.update_ticket(
                TicketUpdateInput(ticket_id=ticket_id, status=status, notes=note)
            )
        else:
            self.tickets.tickets.update_ticket(TicketUpdateInput(ticket_id=ticket_id, notes=note))
        with self.engine.begin() as connection:
            run_id = connection.scalar(
                select(AgentRun.agent_run_id)
                .where(AgentRun.ticket_id == ticket_id)
                .order_by(AgentRun.agent_run_id.desc())
                .limit(1)
            )
            result = connection.execute(
                insert(HumanReview).values(
                    ticket_id=ticket_id,
                    agent_run_id=run_id,
                    action=request.action.value,
                    review_note=note,
                    created_at=self.settings.simulation_now,
                    data_origin="synthetic_operational_data",
                )
            )
            review_id = int(result.inserted_primary_key[0])
        return HumanReviewResult(
            review_id=review_id,
            ticket_id=ticket_id,
            action=request.action,
            ticket_status=status,
            created_at=self.settings.simulation_now,
        )


class DashboardApplicationService:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def summary(self) -> DashboardSummary:
        with self.engine.connect() as connection:
            total = int(connection.scalar(select(func.count()).select_from(Ticket)) or 0)
            status_rows = connection.execute(
                select(Ticket.status, func.count()).group_by(Ticket.status).order_by(Ticket.status)
            ).all()
            decision_rows = connection.execute(
                select(AgentRun.decision, func.count())
                .where(AgentRun.decision.is_not(None))
                .group_by(AgentRun.decision)
                .order_by(AgentRun.decision)
            ).all()
            average = float(connection.scalar(select(func.avg(AgentRun.total_latency_ms))) or 0.0)
            recent = connection.execute(
                select(AgentRun.__table__).order_by(desc(AgentRun.agent_run_id)).limit(10)
            ).mappings().all()
        counts = {str(name): int(count) for name, count in decision_rows}
        return DashboardSummary(
            total_tickets=total,
            tickets_by_status=[CountByName(name=str(name), count=int(count)) for name, count in status_rows],
            runs_by_decision=[CountByName(name=str(name), count=int(count)) for name, count in decision_rows],
            auto_resolve_count=counts.get(Decision.AUTO_RESOLVE.value, 0),
            need_more_info_count=counts.get(Decision.NEED_MORE_INFO.value, 0),
            human_escalation_count=counts.get(Decision.ESCALATE_TO_HUMAN.value, 0),
            average_agent_latency_ms=round(average, 3),
            recent_runs=[TicketApplicationService._run_summary(row) for row in recent],
        )
