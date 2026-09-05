from fastapi import APIRouter, Depends, Query

from customer_support_agent.api.application import HumanReviewApplicationService
from customer_support_agent.api.dependencies import request_id, review_service, run_in_worker, worker_pool
from customer_support_agent.api.schemas import (
    HumanReviewPage,
    HumanReviewRequest,
    HumanReviewResult,
    SuccessEnvelope,
)


router = APIRouter(prefix="/api/v1/human-reviews", tags=["human-review"])


@router.get("", response_model=SuccessEnvelope[HumanReviewPage], summary="List human review queue")
async def list_reviews(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    service: HumanReviewApplicationService = Depends(review_service),
    correlation_id: str = Depends(request_id),
    executor=Depends(worker_pool),  # type: ignore[no-untyped-def]
) -> SuccessEnvelope[HumanReviewPage]:
    return SuccessEnvelope(
        data=await run_in_worker(executor, service.list_reviews, page=page, page_size=page_size),
        request_id=correlation_id,
    )


@router.post(
    "/{ticket_id}", response_model=SuccessEnvelope[HumanReviewResult], summary="Record human review action"
)
async def review_ticket(
    ticket_id: str,
    payload: HumanReviewRequest,
    service: HumanReviewApplicationService = Depends(review_service),
    correlation_id: str = Depends(request_id),
    executor=Depends(worker_pool),  # type: ignore[no-untyped-def]
) -> SuccessEnvelope[HumanReviewResult]:
    return SuccessEnvelope(
        data=await run_in_worker(executor, service.review, ticket_id, payload),
        request_id=correlation_id,
    )
