from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api import health, v1
from app.auth.identity import PERSONA_HEADER
from app.config import Settings, get_settings, validate_settings
from app.crypto import FernetFieldCipher, load_or_create_keys
from app.db import create_engine
from app.db.types import set_field_cipher
from app.error_handlers import UnhandledErrorMiddleware, register_error_handlers
from app.logging import configure_logging
from app.middleware import REQUEST_ID_HEADER, RequestContextMiddleware
from app.security_headers import SecurityHeadersMiddleware

configure_logging()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    validate_settings(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        keys = load_or_create_keys(settings.keys_dir)
        set_field_cipher(FernetFieldCipher(keys.field_keys, keys.fingerprint_key))
        app.state.engine = create_engine(settings.database_url)
        app.state.sessionmaker = async_sessionmaker(app.state.engine, expire_on_commit=False)
        yield
        await app.state.engine.dispose()

    app = FastAPI(title="Patient Dashboard API", lifespan=lifespan)
    app.state.settings = settings
    # Innermost: crashes become our 500 here, so request logging, security headers, and CORS
    # (added after, so they wrap it) still apply to it.
    app.add_middleware(UnhandledErrorMiddleware)
    app.add_middleware(RequestContextMiddleware)
    # HSTS only where TLS is real (production); localhost runs over plain http.
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.env == "production")
    # Outermost, so preflight requests are answered before anything else runs.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type", PERSONA_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(v1.router)
    return app
