"""FastAPI dependency accessors for initialized application services."""

import asyncio
from collections.abc import Callable
from concurrent.futures import Executor
from functools import partial
from typing import TypeVar

from fastapi import Request

from customer_support_agent.api.application import (
    AgentApplicationService,
    DashboardApplicationService,
    HumanReviewApplicationService,
    TicketApplicationService,
)


async def request_id(request: Request) -> str:
    return request.state.request_id


async def ticket_service(request: Request) -> TicketApplicationService:
    return request.app.state.ticket_service


async def agent_service(request: Request) -> AgentApplicationService:
    return request.app.state.agent_service


async def review_service(request: Request) -> HumanReviewApplicationService:
    return request.app.state.review_service


async def dashboard_service(request: Request) -> DashboardApplicationService:
    return request.app.state.dashboard_service


async def worker_pool(request: Request) -> Executor:
    return request.app.state.worker_pool


ResultT = TypeVar("ResultT")


async def run_in_worker(executor: Executor, function: Callable[..., ResultT], *args, **kwargs) -> ResultT:  # type: ignore[no-untyped-def]
    """Run synchronous business code without using the host's broken AnyIO worker path."""
    future = executor.submit(partial(function, *args, **kwargs))
    # This host drops some cross-thread event-loop wakeups. Cooperative polling
    # preserves offloading without depending on call_soon_threadsafe callbacks.
    while not future.done():
        await asyncio.sleep(0.005)
    return future.result()
