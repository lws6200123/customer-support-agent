"""Persistence and query service for sanitized Agent runtime traces."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Engine, func, insert, select, update
from sqlalchemy.exc import SQLAlchemyError

from customer_support_agent.agent.schemas import AgentRunStatus, AgentTrace, AgentTraceStep
from customer_support_agent.core.errors import DatabaseError, InvalidInputError
from customer_support_agent.core.security import sanitize_text
from customer_support_agent.core.schemas import Decision
from customer_support_agent.db.models import AgentRun, AgentStep


class AgentTraceService:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def start_run(
        self,
        *,
        ticket_id: str | None,
        customer_id: str | None,
        order_id: str | None,
        user_message: str,
        started_at: datetime,
    ) -> int:
        try:
            with self.engine.begin() as connection:
                result = connection.execute(
                    insert(AgentRun).values(
                        ticket_id=ticket_id,
                        customer_id=customer_id,
                        order_id=order_id,
                        user_message=sanitize_text(user_message) or "",
                        intent=None,
                        decision=None,
                        status=AgentRunStatus.RUNNING.value,
                        started_at=started_at,
                        completed_at=None,
                        total_latency_ms=None,
                        tool_call_count=0,
                        error_summary=None,
                        final_response=None,
                        agent_summary=None,
                    )
                )
                return int(result.inserted_primary_key[0])
        except SQLAlchemyError as exc:
            raise DatabaseError() from exc

    def update_context(
        self,
        run_id: int,
        *,
        ticket_id: str | None,
        customer_id: str | None,
        order_id: str | None,
        intent: str | None,
    ) -> None:
        try:
            with self.engine.begin() as connection:
                connection.execute(
                    update(AgentRun)
                    .where(AgentRun.agent_run_id == run_id)
                    .values(
                        ticket_id=ticket_id,
                        customer_id=customer_id,
                        order_id=order_id,
                        intent=intent,
                    )
                )
        except SQLAlchemyError as exc:
            raise DatabaseError() from exc

    def record_step(
        self,
        run_id: int,
        *,
        node_name: str,
        action: str | None = None,
        tool_name: str | None = None,
        status: str,
        latency_ms: float,
        input_summary: str | None = None,
        output_summary: str | None = None,
        error_code: str | None = None,
        created_at: datetime,
    ) -> int:
        try:
            with self.engine.begin() as connection:
                sequence = int(
                    connection.scalar(
                        select(func.coalesce(func.max(AgentStep.step_sequence), 0)).where(
                            AgentStep.agent_run_id == run_id
                        )
                    )
                    or 0
                ) + 1
                connection.execute(
                    insert(AgentStep).values(
                        agent_run_id=run_id,
                        step_sequence=sequence,
                        node_name=node_name,
                        action=action,
                        tool_name=tool_name,
                        status=status,
                        latency_ms=round(max(latency_ms, 0.0), 3),
                        input_summary=sanitize_text(input_summary),
                        output_summary=sanitize_text(output_summary),
                        error_code=error_code,
                        created_at=created_at,
                    )
                )
                return sequence
        except SQLAlchemyError as exc:
            raise DatabaseError() from exc

    def finish_run(
        self,
        run_id: int,
        *,
        status: AgentRunStatus,
        decision: Decision | None,
        completed_at: datetime,
        total_latency_ms: float,
        tool_call_count: int,
        error_codes: list[str],
        final_response: str | None,
        agent_summary: str | None,
    ) -> None:
        try:
            with self.engine.begin() as connection:
                connection.execute(
                    update(AgentRun)
                    .where(AgentRun.agent_run_id == run_id)
                    .values(
                        status=status.value,
                        decision=decision.value if decision else None,
                        completed_at=completed_at,
                        total_latency_ms=round(max(total_latency_ms, 0.0), 3),
                        tool_call_count=tool_call_count,
                        error_summary=",".join(sorted(set(error_codes))) or None,
                        final_response=sanitize_text(final_response),
                        agent_summary=sanitize_text(agent_summary),
                    )
                )
        except SQLAlchemyError as exc:
            raise DatabaseError() from exc

    def get_trace(self, run_id: int) -> AgentTrace:
        try:
            with self.engine.connect() as connection:
                run = connection.execute(
                    select(AgentRun.__table__).where(AgentRun.agent_run_id == run_id)
                ).mappings().first()
                steps = connection.execute(
                    select(AgentStep.__table__)
                    .where(AgentStep.agent_run_id == run_id)
                    .order_by(AgentStep.step_sequence)
                ).mappings().all()
        except SQLAlchemyError as exc:
            raise DatabaseError() from exc
        if run is None:
            raise InvalidInputError(f"Agent run not found: {run_id}")
        return AgentTrace(
            **dict(run),
            steps=[AgentTraceStep.model_validate(dict(row)) for row in steps],
        )
