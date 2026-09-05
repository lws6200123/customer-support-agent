from fastapi import APIRouter, Depends

from customer_support_agent.api.application import DashboardApplicationService
from customer_support_agent.api.dependencies import dashboard_service, request_id, run_in_worker, worker_pool
from customer_support_agent.api.schemas import DashboardSummary, SuccessEnvelope


router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=SuccessEnvelope[DashboardSummary], summary="Get dashboard metrics")
async def dashboard_summary(
    service: DashboardApplicationService = Depends(dashboard_service),
    correlation_id: str = Depends(request_id),
    executor=Depends(worker_pool),  # type: ignore[no-untyped-def]
) -> SuccessEnvelope[DashboardSummary]:
    return SuccessEnvelope(
        data=await run_in_worker(executor, service.summary), request_id=correlation_id
    )
