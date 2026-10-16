import logging
import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.logging import request_id_var

logger = logging.getLogger("app.request")

REQUEST_ID_HEADER = "X-Request-ID"


def _incoming_request_id(headers: Headers) -> str | None:
    """Reuse a caller's ID only if it is a UUID, so nothing arbitrary reaches the logs."""
    raw = headers.get(REQUEST_ID_HEADER)
    if raw is None:
        return None
    try:
        return str(uuid.UUID(raw))
    except ValueError:
        return None


class RequestContextMiddleware:
    """Assigns a request ID, echoes it in `X-Request-ID`, and logs one line per request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _incoming_request_id(Headers(scope=scope)) or str(uuid.uuid4())
        # Also kept on the scope so error handlers outside this middleware can read it.
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        status = 500  # if the app raises before responding, the error handler answers 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            route = scope.get("route")
            logger.info(
                "request",
                extra={
                    "ctx": {
                        "request_id": request_id,
                        "method": scope["method"],
                        # The route template, never the raw path or query string.
                        "route": getattr(route, "path", "unmatched"),
                        "status": status,
                        "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                    }
                },
            )
            request_id_var.reset(token)
