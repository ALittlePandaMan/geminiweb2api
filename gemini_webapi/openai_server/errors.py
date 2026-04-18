from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from gemini_webapi.exceptions import (
    APIError,
    AuthError,
    GeminiError,
    ModelInvalid,
    TemporarilyBlocked,
    TimeoutError as GeminiTimeoutError,
    UsageLimitExceeded,
)


class OpenAIHTTPException(Exception):
    def __init__(
        self,
        status_code: int,
        message: str,
        error_type: str,
        code: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.message = message
        self.error_type = error_type
        self.code = code
        self.headers = headers
        super().__init__(message)


def error_body(message: str, error_type: str, code: str | None = None) -> dict:
    return {
        "error": {
            "message": message,
            "type": error_type,
            "param": None,
            "code": code,
        }
    }


def map_gemini_exception(exc: Exception) -> OpenAIHTTPException:
    if isinstance(exc, OpenAIHTTPException):
        return exc
    if isinstance(exc, ValueError):
        return OpenAIHTTPException(
            status_code=400,
            message=str(exc),
            error_type="invalid_request_error",
            code="invalid_request",
        )
    if isinstance(exc, ModelInvalid):
        return OpenAIHTTPException(
            status_code=400,
            message=str(exc),
            error_type="invalid_request_error",
            code="invalid_model",
        )
    if isinstance(exc, (UsageLimitExceeded, TemporarilyBlocked)):
        return OpenAIHTTPException(
            status_code=429,
            message=str(exc),
            error_type="rate_limit_error",
            code="rate_limited",
        )
    if isinstance(exc, (AuthError, GeminiTimeoutError)):
        return OpenAIHTTPException(
            status_code=503,
            message=str(exc),
            error_type="server_error",
            code="gemini_unavailable",
        )
    if isinstance(exc, APIError):
        return OpenAIHTTPException(
            status_code=502,
            message=str(exc),
            error_type="server_error",
            code="upstream_protocol_error",
        )
    if isinstance(exc, GeminiError):
        return OpenAIHTTPException(
            status_code=503,
            message=str(exc),
            error_type="server_error",
            code="gemini_error",
        )
    return OpenAIHTTPException(
        status_code=500,
        message="Unexpected internal error",
        error_type="server_error",
        code="internal_error",
    )


async def openai_exception_handler(
    request: Request,
    exc: OpenAIHTTPException,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(exc.message, exc.error_type, exc.code),
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=error_body(
            "Request validation failed",
            "invalid_request_error",
            "validation_error",
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(OpenAIHTTPException, openai_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)


def invalid_api_key_exception() -> OpenAIHTTPException:
    return OpenAIHTTPException(
        status_code=401,
        message="Invalid API key",
        error_type="authentication_error",
        code="invalid_api_key",
        headers={"WWW-Authenticate": "Bearer"},
    )
