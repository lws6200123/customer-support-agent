from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from concurrent.futures import Executor
from queue import Empty, Queue

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from customer_support_agent.api.application import AgentApplicationService
from customer_support_agent.api.dependencies import agent_service, request_id, run_in_worker, worker_pool
from customer_support_agent.api.schemas import (
    AgentRunRequest,
    AgentRunResult,
    AgentRunSummary,
    SuccessEnvelope,
    TraceSteps,
)


router = APIRouter(prefix="/api/v1", tags=["agent"])
logger = logging.getLogger("customer_support_agent.api.agent")


@router.post("/agent/run", response_model=SuccessEnvelope[AgentRunResult], summary="Run support Agent")
async def run_agent(
    payload: AgentRunRequest,
    service: AgentApplicationService = Depends(agent_service),
    correlation_id: str = Depends(request_id),
    executor: Executor = Depends(worker_pool),
) -> SuccessEnvelope[AgentRunResult]:
    data = await run_in_worker(executor, service.run, payload)
    logger.info(
        "request_id=%s run_id=%s ticket_id=%s decision=%s",
        correlation_id,
        data.run_id,
        data.ticket_id,
        data.decision.value,
    )
    return SuccessEnvelope(data=data, request_id=correlation_id)


def _sse(event) -> str:  # type: ignore[no-untyped-def]
    return f"event: {event.event}\ndata: {event.model_dump_json()}\n\n"


async def _event_stream(
    service: AgentApplicationService,
    payload: AgentRunRequest,
    executor: Executor,
    correlation_id: str,
) -> AsyncIterator[str]:
    queue: Queue[object] = Queue()
    sentinel = object()

    def produce() -> None:
        try:
            for event in service.stream(payload):
                queue.put(event)
        finally:
            queue.put(sentinel)

    worker = executor.submit(produce)
    while True:
        try:
            item = queue.get_nowait()
        except Empty:
            await asyncio.sleep(0.005)
            continue
        if item is sentinel:
            break
        if item.event == "run_completed":  # type: ignore[union-attr]
            logger.info(
                "request_id=%s run_id=%s ticket_id=%s decision=%s stream=true",
                correlation_id,
                item.run_id,  # type: ignore[union-attr]
                item.ticket_id,  # type: ignore[union-attr]
                item.decision,  # type: ignore[union-attr]
            )
        yield _sse(item)
    worker.result()


@router.post(
    "/agent/run/stream",
    response_class=StreamingResponse,
    summary="Stream support Agent events with POST SSE",
    description="Consume with fetch plus ReadableStream; browser EventSource cannot POST.",
)
async def stream_agent(
    payload: AgentRunRequest,
    service: AgentApplicationService = Depends(agent_service),
    executor: Executor = Depends(worker_pool),
    correlation_id: str = Depends(request_id),
) -> StreamingResponse:
    return StreamingResponse(
        _event_stream(service, payload, executor, correlation_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get(
    "/agent-runs/{run_id}", response_model=SuccessEnvelope[AgentRunSummary], summary="Get Agent run"
)
async def get_run(
    run_id: int,
    service: AgentApplicationService = Depends(agent_service),
    correlation_id: str = Depends(request_id),
    executor: Executor = Depends(worker_pool),
) -> SuccessEnvelope[AgentRunSummary]:
    return SuccessEnvelope(
        data=await run_in_worker(executor, service.get_run, run_id), request_id=correlation_id
    )


@router.get(
    "/agent-runs/{run_id}/steps",
    response_model=SuccessEnvelope[TraceSteps],
    summary="Get ordered Agent trace steps",
)
async def get_steps(
    run_id: int,
    service: AgentApplicationService = Depends(agent_service),
    correlation_id: str = Depends(request_id),
    executor: Executor = Depends(worker_pool),
) -> SuccessEnvelope[TraceSteps]:
    return SuccessEnvelope(
        data=await run_in_worker(executor, service.get_steps, run_id), request_id=correlation_id
    )
