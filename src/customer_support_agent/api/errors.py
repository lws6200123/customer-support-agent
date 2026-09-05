"""Safe exception normalization for API boundaries."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from customer_support_agent.core.errors import DomainError, ErrorCode


logger = logging.getLogger(__name__)


class ApiConflictError(RuntimeError):
    pass


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def _error(status: int, code: str, message: str, request: Request) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "ok": False,
            "error": {"code": code, "message": message},
            "request_id": _request_id(request),
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, _exc: RequestValidationError) -> JSONResponse:
        return _error(422, "VALIDATION_ERROR", "Request validation failed.", request)

    @app.exception_handler(ApiConflictError)
    async def conflict_error(request: Request, exc: ApiConflictError) -> JSONResponse:
        return _error(409, "INVALID_STATE_TRANSITION", str(exc), request)

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError) -> JSONResponse:
        if exc.code in {ErrorCode.TICKET_NOT_FOUND, ErrorCode.RUN_NOT_FOUND}:
            status = 404
        elif exc.code in {ErrorCode.LLM_CONFIG_MISSING, ErrorCode.LLM_UNAVAILABLE}:
            status = 503
        elif exc.code in {
            ErrorCode.KNOWLEDGE_CONFIG_MISSING,
            ErrorCode.KNOWLEDGE_SERVICE_UNAVAILABLE,
        }:
            status = 503
        elif exc.code == ErrorCode.DATABASE_ERROR:
            status = 500
        else:
            status = 400
        return _error(status, exc.code.value, exc.safe_message, request)

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled API error request_id=%s", _request_id(request))
        del exc
        return _error(500, "INTERNAL_ERROR", "An internal error occurred.", request)
