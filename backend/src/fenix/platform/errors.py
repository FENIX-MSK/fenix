"""Uniform API error contract: every error body is `{"error": {"code", "message", "details"}}`."""

import re
from collections.abc import Callable, Coroutine
from http import HTTPStatus
from typing import Any

import structlog
from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException

log = structlog.get_logger()


class ErrorBody(BaseModel):
    code: str = Field(description="Machine-readable snake_case code, e.g. not_found")
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorBody


class ApiError(Exception):
    """Domain-level error raised by routes and mapped to the uniform body."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details or {}))
    return JSONResponse(jsonable_encoder(body), status_code=status_code, headers=headers)


def _code_for_status(status_code: int) -> str:
    try:
        phrase = HTTPStatus(status_code).phrase
    except ValueError:
        return "http_error"
    return re.sub(r"[^a-z0-9]+", "_", phrase.lower()).strip("_")


async def _handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
    return error_response(exc.status_code, exc.code, exc.message, exc.details)


async def _handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
    code = _code_for_status(exc.status_code)
    detail: Any = exc.detail
    return error_response(
        exc.status_code,
        code,
        detail if isinstance(detail, str) else code,
        detail if isinstance(detail, dict) else None,
        headers=dict(exc.headers) if exc.headers else None,
    )


async def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response(
        HTTPStatus.UNPROCESSABLE_CONTENT,
        "validation_error",
        "Request validation failed",
        {"errors": jsonable_encoder(exc.errors())},
    )


async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    # The traceback goes to the log only; the client gets an opaque body.
    log.exception("http.unhandled_error", method=request.method, path=request.url.path)
    return error_response(
        HTTPStatus.INTERNAL_SERVER_ERROR, "internal_error", "Internal server error"
    )


# Passed to FastAPI(exception_handlers=...), whose signature accepts handlers of a
# concrete exception type; most specific first for readability, lookup is by MRO.
EXCEPTION_HANDLERS: dict[
    int | type[Exception], Callable[[Request, Any], Coroutine[Any, Any, Response]]
] = {
    ApiError: _handle_api_error,
    HTTPException: _handle_http_exception,
    RequestValidationError: _handle_validation_error,
    Exception: _handle_unexpected,
}
