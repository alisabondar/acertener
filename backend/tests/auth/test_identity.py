import uuid

import httpx2
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.demo.personas import PERSONAS
from tests.factories import make_user

pytestmark = [pytest.mark.db, pytest.mark.anyio]


async def _add(session: AsyncSession, **overrides: object) -> User:
    user = make_user(**overrides)
    session.add(user)
    await session.flush()
    return user


async def test_me_returns_the_persona(api: httpx2.AsyncClient, db_session: AsyncSession) -> None:
    nurse = await _add(db_session, name="Sam Okafor", role="nurse", credential="RN")

    response = await api.get("/api/v1/auth/me", headers={"X-Persona": str(nurse.id)})

    assert response.status_code == 200
    assert response.json() == {
        "id": str(nurse.id),
        "name": "Sam Okafor",
        "role": "nurse",
        "credential": "RN",
    }


@pytest.mark.parametrize("header", [None, "not-a-uuid", str(uuid.uuid4()), "inactive"])
async def test_requests_without_a_valid_persona_are_rejected(
    api: httpx2.AsyncClient, db_session: AsyncSession, header: str | None
) -> None:
    if header == "inactive":
        header = str((await _add(db_session, is_active=False)).id)
    headers = {"X-Persona": header} if header else {}

    response = await api.get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 401
    assert response.json()["code"] == "NOT_AUTHENTICATED"


async def test_personas_are_listed_in_order_without_other_staff(
    api: httpx2.AsyncClient, db_session: AsyncSession
) -> None:
    for persona in reversed(PERSONAS):
        await _add(
            db_session,
            name=persona.name,
            email=persona.email,
            role=persona.role,
            credential=persona.credential,
        )
    await _add(db_session, name="Other Staff")

    response = await api.get("/api/v1/personas")

    assert response.status_code == 200
    assert [p["name"] for p in response.json()] == [p.name for p in PERSONAS]


@pytest.mark.parametrize("demo_mode", [False])
@pytest.mark.parametrize("path", ["/api/v1/auth/me", "/api/v1/personas"])
async def test_nothing_works_outside_demo_mode(
    api: httpx2.AsyncClient, db_session: AsyncSession, path: str
) -> None:
    user = await _add(db_session)

    response = await api.get(path, headers={"X-Persona": str(user.id)})

    assert response.status_code == 401
