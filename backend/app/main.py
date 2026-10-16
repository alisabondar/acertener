from fastapi import FastAPI

from app.api import health, v1
from app.error_handlers import register_error_handlers
from app.logging import configure_logging
from app.middleware import RequestContextMiddleware


def create_app() -> FastAPI:
    app = FastAPI(title="Patient Dashboard API")
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(v1.router)
    return app


configure_logging()
app = create_app()
