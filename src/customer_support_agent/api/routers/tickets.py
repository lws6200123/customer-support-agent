from fastapi import APIRouter, Depends, Query

from customer_support_agent.agent.schemas import Intent
from customer_support_agent.api.application import TicketApplicationService
from customer_support_agent.api.dependencies import request_id, run_in_worker, ticket_service, worker_pool
from customer_support_agent.api.schemas import (
    SuccessEnvelope,
    TicketCreateRequest,
    TicketCreated,
    TicketDetail,
    TicketPage,
)
from customer_support_agent.core.schemas import Decision, TicketStatus


router = APIRouter(prefix="/api/v1/tickets", tags=["tickets"])


@router.get("", response_model=SuccessEnvelope[TicketPage], summary="List support tickets")
async def list_tickets(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: TicketStatus | None = None,
    decision: Decision | None = None,
    intent: Intent | None = None,
    service: TicketApplicationService = Depends(ticket_service),
    correlation_id: str = Depends(request_id),
    executor=Depends(worker_pool),  # type: ignore[no-untyped-def]
) -> SuccessEnvelope[TicketPage]:
    return SuccessEnvelope(
        data=await run_in_worker(
            executor,
            service.list_tickets,
            page=page, page_size=page_size, status=status, decision=decision, intent=intent
        ),
        request_id=correlation_id,
    )


@router.post("", response_model=SuccessEnvelope[TicketCreated], status_code=201, summary="Create demo ticket")
async def create_ticket(
    payload: TicketCreateRequest,
    service: TicketApplicationService = Depends(ticket_service),
    correlation_id: str = Depends(request_id),
    executor=Depends(worker_pool),  # type: ignore[no-untyped-def]
) -> SuccessEnvelope[TicketCreated]:
    return SuccessEnvelope(
        data=await run_in_worker(executor, service.create_ticket, payload), request_id=correlation_id
    )


@router.get("/{ticket_id}", response_model=SuccessEnvelope[TicketDetail], summary="Get ticket detail")
async def get_ticket(
    ticket_id: str,
    service: TicketApplicationService = Depends(ticket_service),
    correlation_id: str = Depends(request_id),
    executor=Depends(worker_pool),  # type: ignore[no-untyped-def]
) -> SuccessEnvelope[TicketDetail]:
    return SuccessEnvelope(
        data=await run_in_worker(executor, service.get_ticket_detail, ticket_id),
        request_id=correlation_id,
    )
