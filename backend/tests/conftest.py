import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx2
import pytest
from alembic import command
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.crypto import FernetFieldCipher
from app.db import create_engine
from app.db.session import get_session
from app.db.types import set_field_cipher
from app.main import create_app
from tests.helpers import alembic_config

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://app:app@localhost:5432/app_test"
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def isolated_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests see only the settings they pass, not the shell's or container's (ENV, DEMO_MODE...)."""
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None, env="test", database_url=TEST_DATABASE_URL, keys_dir=tmp_path / "keys"
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture(autouse=True)
def field_cipher() -> Iterator[FernetFieldCipher]:
    cipher = FernetFieldCipher([Fernet.generate_key()], Fernet.generate_key())
    set_field_cipher(cipher)
    yield cipher
    set_field_cipher(None)


@pytest.fixture(scope="session")
def migrated_database() -> str:
    command.upgrade(alembic_config(TEST_DATABASE_URL), "head")
    return TEST_DATABASE_URL


@pytest.fixture
async def db_session(migrated_database: str) -> AsyncIterator[AsyncSession]:
    """A session whose work is rolled back after each test, even if the test commits."""
    engine = create_engine(migrated_database)
    async with engine.connect() as conn:
        transaction = await conn.begin()
        session = AsyncSession(
            bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
    await engine.dispose()


@pytest.fixture
def demo_mode() -> bool:
    return True


@pytest.fixture
def app(settings: Settings, demo_mode: bool) -> FastAPI:
    return create_app(settings.model_copy(update={"demo_mode": demo_mode}))


@pytest.fixture
async def api(app: FastAPI, db_session: AsyncSession) -> AsyncIterator[httpx2.AsyncClient]:
    """The app called in-process, sharing the test's rolled-back database session."""

    async def test_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = test_session
    # Sessions the app opens itself (e.g. background audit writes) join the test's
    # transaction through savepoints, so their commits are rolled back too.
    app.state.sessionmaker = async_sessionmaker(
        bind=await db_session.connection(),
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    # Like a real client: unhandled errors arrive as 500 responses, not raised exceptions.
    transport = httpx2.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
