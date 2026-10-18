from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

DOCS_PATHS = ("/docs", "/redoc")

BASE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}
# API responses are JSON that may contain PHI: nothing may cache, render, or frame them.
API_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}
# Swagger UI loads its assets from jsDelivr and its favicon from fastapi.tiangolo.com.
DOCS_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; frame-ancestors 'none'; connect-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data: https://fastapi.tiangolo.com"
    ),
}
HSTS = {"Strict-Transport-Security": "max-age=31536000; includeSubDomains"}


class SecurityHeadersMiddleware:
    """Adds browser security headers to every HTTP response."""

    def __init__(self, app: ASGIApp, *, hsts: bool) -> None:
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        extra = DOCS_HEADERS if scope["path"].startswith(DOCS_PATHS) else API_HEADERS

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in {**BASE_HEADERS, **extra, **(HSTS if self.hsts else {})}.items():
                    headers[name] = value
            await send(message)

        await self.app(scope, receive, send_with_headers)
