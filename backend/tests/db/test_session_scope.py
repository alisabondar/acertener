from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI
from fastapi.testclient import TestClient

from app.db.session import DbSession


def test_the_request_session_is_released_before_background_work_runs() -> None:
    """Background audit writes take their own connection; if the request still held its own,
    a busy pool would deadlock with every request waiting for a second connection."""
    events: list[str] = []

    @asynccontextmanager
    async def sessionmaker() -> AsyncIterator[object]:
        events.append("session opened")
        yield object()
        events.append("session closed")

    app = FastAPI()
    app.state.sessionmaker = sessionmaker

    @app.get("/")
    async def endpoint(session: DbSession, background: BackgroundTasks) -> None:
        background.add_task(events.append, "background ran")

    with TestClient(app) as client:
        client.get("/")

    assert events == ["session opened", "session closed", "background ran"]
