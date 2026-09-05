from fastapi import APIRouter, Depends, Request
from sqlalchemy import text

from customer_support_agent.api.dependencies import request_id, run_in_worker, worker_pool
from customer_support_agent.api.schemas import HealthData, ReadinessData, SuccessEnvelope


router = APIRouter(tags=["health"])


@router.get("/health", response_model=SuccessEnvelope[HealthData], summary="Service liveness")
async def health(request: Request, correlation_id: str = Depends(request_id)) -> SuccessEnvelope[HealthData]:
    return SuccessEnvelope(
        data=HealthData(status="ok", service=request.app.title, version=request.app.version),
        request_id=correlation_id,
    )


@router.get("/ready", response_model=SuccessEnvelope[ReadinessData], summary="Dependency readiness")
async def ready(
    request: Request,
    correlation_id: str = Depends(request_id),
    executor=Depends(worker_pool),  # type: ignore[no-untyped-def]
) -> SuccessEnvelope[ReadinessData]:
    database = "available"
    try:
        def check_database() -> None:
            with request.app.state.engine.connect() as connection:
                connection.execute(text("SELECT 1"))

        await run_in_worker(executor, check_database)
    except Exception:
        database = "unavailable"
    settings = request.app.state.settings
    data = ReadinessData(
        status="ready" if database == "available" else "not_ready",
        database=database,
        llm_configured=settings.deepseek_configured,
        ragflow_configured=settings.ragflow_configured,
    )
    return SuccessEnvelope(data=data, request_id=correlation_id)
