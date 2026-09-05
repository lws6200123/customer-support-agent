"""FastAPI application factory for the Stage 6 local service."""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine

from customer_support_agent.agent.workflow import SupportAgentWorkflow
from customer_support_agent.api.application import (
    AgentApplicationService,
    DashboardApplicationService,
    HumanReviewApplicationService,
    TicketApplicationService,
    WorkflowFactory,
)
from customer_support_agent.api.errors import register_error_handlers
from customer_support_agent.api.routers import agent, dashboard, health, reviews, tickets
from customer_support_agent.core.config import AppSettings
from customer_support_agent.db.engine import create_sqlite_engine
from customer_support_agent.db.models import HumanReview
from customer_support_agent.llm.adapter import DeepSeekChatModel


VERSION = "0.1.0"
logger = logging.getLogger("customer_support_agent.api")


def _default_workflow_factory(settings: AppSettings, engine: Engine) -> WorkflowFactory:
    def factory() -> SupportAgentWorkflow:
        return SupportAgentWorkflow(DeepSeekChatModel(settings), engine=engine, settings=settings)

    return factory


def create_app(
    *,
    settings: AppSettings | None = None,
    engine: Engine | None = None,
    workflow_factory: WorkflowFactory | None = None,
) -> FastAPI:
    runtime_settings = settings or AppSettings()
    runtime_engine = engine or create_sqlite_engine(runtime_settings.database_path)
    runtime_factory = workflow_factory or _default_workflow_factory(runtime_settings, runtime_engine)
    worker_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="support-api")

    @asynccontextmanager
    async def lifespan(_app: FastAPI):  # type: ignore[no-untyped-def]
        # Additive, idempotent Stage 6 table initialization; no data rebuild occurs.
        HumanReview.__table__.create(runtime_engine, checkfirst=True)
        try:
            yield
        finally:
            worker_pool.shutdown(wait=True, cancel_futures=True)

    docs_enabled = runtime_settings.app_env.casefold() == "development"
    app = FastAPI(
        title="Customer Support Ticket Agent API",
        version=VERSION,
        description=(
            "Local demo API for the guarded LangGraph support workflow. "
            "AUTO_RESOLVE never executes a financial refund."
        ),
        docs_url="/docs" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
        lifespan=lifespan,
    )
    app.state.settings = runtime_settings
    app.state.engine = runtime_engine
    app.state.worker_pool = worker_pool
    app.state.ticket_service = TicketApplicationService(runtime_engine, runtime_settings)
    app.state.agent_service = AgentApplicationService(
        runtime_engine, runtime_settings, runtime_factory
    )
    app.state.review_service = HumanReviewApplicationService(runtime_engine, runtime_settings)
    app.state.dashboard_service = DashboardApplicationService(runtime_engine)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next: Callable):  # type: ignore[no-untyped-def]
        correlation_id = request.headers.get("X-Request-ID", "").strip()[:128] or str(uuid4())
        request.state.request_id = correlation_id
        started = perf_counter()
        response = await call_next(request)
        latency_ms = (perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = correlation_id
        logger.info(
            "request_id=%s method=%s path=%s status_code=%s latency_ms=%.3f",
            correlation_id,
            request.method,
            request.url.path,
            response.status_code,
            latency_ms,
        )
        return response

    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(tickets.router)
    app.include_router(agent.router)
    app.include_router(reviews.router)
    app.include_router(dashboard.router)
    return app


app = create_app()
