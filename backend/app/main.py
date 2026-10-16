from fastapi import FastAPI

from app.api import health, v1
from app.logging import configure_logging
from app.middleware import RequestContextMiddleware


def create_app() -> FastAPI:
    app = FastAPI(title="Patient Dashboard API")
    app.add_middleware(RequestContextMiddleware)
    app.include_router(health.router)
    app.include_router(v1.router)
    return app


# Logging is process-wide, so it's configured once here, not per app instance.
configure_logging()
app = create_app()
