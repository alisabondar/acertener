from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import health, v1
from app.config import Settings, get_settings
from app.db import create_engine
from app.error_handlers import register_error_handlers
from app.logging import configure_logging
from app.middleware import RequestContextMiddleware

configure_logging()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.engine = create_engine(settings.database_url)
        yield
        await app.state.engine.dispose()

    app = FastAPI(title="Patient Dashboard API", lifespan=lifespan)
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(v1.router)
    return app
