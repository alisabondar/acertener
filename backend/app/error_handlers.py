import logging
from collections.abc import Mapping, Sequence
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.errors import AppError, ErrorCode
from app.middleware import REQUEST_ID_HEADER

logger = logging.getLogger("app.errors")

PROBLEM_JSON = "application/problem+json"


def problem(
    request: Request,
    status: int,
    code: str,
    detail: str,
    errors: dict[str, str] | None = None,
    headers: Mapping[str, str] | None = None,
    extensions: Mapping[str, object] | None = None,
) -> JSONResponse:
    request_id: str | None = getattr(request.state, "request_id", None)
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": HTTPStatus(status).phrase,
        "status": status,
        "detail": detail,
        "code": code,
        "request_id": request_id,
    }
    if errors is not None:
        body["errors"] = errors
    if extensions:
        body.update(extensions)
    headers = dict(headers or {})
    if request_id:
        headers[REQUEST_ID_HEADER] = request_id
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON, headers=headers)


def _field_key(loc: Sequence[str | int]) -> str:
    parts = [str(p) for p in loc]
    if parts and parts[0] == "body":
        parts = parts[1:]
    return ".".join(parts) or "body"


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError) -> JSONResponse:
        return problem(
            request,
            exc.code.status,
            exc.code.name,
            exc.detail,
            headers=exc.response_headers(),
            extensions=exc.extensions,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors: dict[str, str] = {}
        for err in exc.errors():
            # Only the location and message: Pydantic's `input` could be PHI.
            errors.setdefault(_field_key(err["loc"]), err["msg"])
        code = ErrorCode.VALIDATION_FAILED
        return problem(request, code.status, code.name, code.detail, errors)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # `exc.detail` is never returned: callers may have put PHI in it.
        status = HTTPStatus(exc.status_code)
        registered = ErrorCode.__members__.get(status.name)
        detail = registered.detail if registered else status.description
        # Keep protocol headers such as `Allow` (405) and `WWW-Authenticate` (401).
        return problem(request, status, status.name, detail, headers=exc.headers)


async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    # The type only: exception messages and tracebacks can contain PHI.
    logger.error(
        "unhandled_exception",
        extra={"ctx": {"request_id": request_id, "exc_type": type(exc).__name__}},
    )
    code = ErrorCode.INTERNAL_ERROR
    return problem(request, code.status, code.name, code.detail)


class UnhandledErrorMiddleware:
    """Turns crashes into the generic 500 *inside* the middleware stack.

    Starlette's own fallback runs outermost, so its 500s would skip CORS (the browser
    couldn't read the error) and the security headers. Register this innermost.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception as exc:
            if started:  # too late for a clean response; let the server close it
                raise
            response = await unhandled_error(Request(scope), exc)
            await response(scope, receive, send)
