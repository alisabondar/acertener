import logging

from fastapi import APIRouter, Request
from sqlalchemy import text

from app.errors import ServiceUnavailableError

router = APIRouter(tags=["health"])
logger = logging.getLogger("app.health")


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness: the process is up."""
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(request: Request) -> dict[str, str]:
    """Readiness: dependencies are reachable."""
    try:
        async with request.app.state.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # any failure means not ready, including raw driver errors
        # The type only: driver messages include the host, user, and database name.
        logger.warning("database_unavailable", extra={"ctx": {"exc_type": type(exc).__name__}})
        raise ServiceUnavailableError from None
    return {"status": "ready"}
