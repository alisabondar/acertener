import uuid

import httpx2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.demo.personas import PERSONAS
from app.main import create_app
from tests.factories import add_user, persona_headers

pytestmark = [pytest.mark.db, pytest.mark.anyio]


async def test_me_returns_the_persona(api: httpx2.AsyncClient, db_session: AsyncSession) -> None:
    nurse = await add_user(db_session, name="Sam Okafor", role="nurse", credential="RN")

    response = await api.get("/api/v1/auth/me", headers=persona_headers(nurse))

    assert response.status_code == 200
    body = response.json()
    assert (body["id"], body["name"], body["role"], body["credential"]) == (
        str(nurse.id),
        "Sam Okafor",
        "nurse",
        "RN",
    )


@pytest.mark.parametrize("header", [None, "not-a-uuid", str(uuid.uuid4()), "inactive"])
async def test_requests_without_a_valid_persona_are_rejected(
    api: httpx2.AsyncClient, db_session: AsyncSession, header: str | None
) -> None:
    if header == "inactive":
        header = str((await add_user(db_session, is_active=False)).id)
    headers = {"X-Persona": header} if header else {}

    response = await api.get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 401
    assert response.json()["code"] == "NOT_AUTHENTICATED"


async def test_personas_are_listed_in_order_without_other_staff(
    api: httpx2.AsyncClient, db_session: AsyncSession
) -> None:
    for persona in reversed(PERSONAS):
        await add_user(
            db_session,
            name=persona.name,
            email=persona.email,
            role=persona.role,
            credential=persona.credential,
        )
    await add_user(db_session, name="Other Staff")

    response = await api.get("/api/v1/personas")

    assert response.status_code == 200
    assert [p["name"] for p in response.json()] == [p.name for p in PERSONAS]


@pytest.mark.parametrize("demo_mode", [False])
@pytest.mark.parametrize("path", ["/api/v1/auth/me", "/api/v1/personas"])
async def test_nothing_works_outside_demo_mode(
    api: httpx2.AsyncClient, db_session: AsyncSession, path: str
) -> None:
    user = await add_user(db_session)

    response = await api.get(path, headers=persona_headers(user))

    assert response.status_code == 401


def test_requests_use_a_real_per_request_session(settings: Settings) -> None:
    """Every other test swaps in the test session; this one goes through the real one."""
    app = create_app(settings.model_copy(update={"demo_mode": True}))

    with TestClient(app) as client:
        response = client.get("/api/v1/auth/me", headers={"X-Persona": str(uuid.uuid4())})

    assert response.status_code == 401
