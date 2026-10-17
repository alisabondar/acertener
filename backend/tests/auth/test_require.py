from typing import Annotated

import httpx2
import pytest
from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import Permission, require
from app.db.models import User
from tests.factories import add_user, persona_headers

pytestmark = [pytest.mark.db, pytest.mark.anyio]


@pytest.fixture(autouse=True)
def clinical_route(app: FastAPI) -> None:
    @app.get("/test/clinical")
    async def clinical(user: Annotated[User, Depends(require(Permission.VIEW_CLINICAL))]) -> str:
        return user.name


async def test_allowed_role_gets_through(api: httpx2.AsyncClient, db_session: AsyncSession) -> None:
    user = await add_user(db_session, "nurse", name="A nurse")
    response = await api.get("/test/clinical", headers=persona_headers(user))

    assert response.status_code == 200
    assert response.json() == "A nurse"


async def test_disallowed_role_is_forbidden(
    api: httpx2.AsyncClient, db_session: AsyncSession
) -> None:
    user = await add_user(db_session, "front_desk", name="A front_desk")
    response = await api.get("/test/clinical", headers=persona_headers(user))

    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"


async def test_identity_is_checked_before_permissions(api: httpx2.AsyncClient) -> None:
    response = await api.get("/test/clinical")

    assert response.status_code == 401


async def test_me_lists_the_role_permissions(
    api: httpx2.AsyncClient, db_session: AsyncSession
) -> None:
    user = await add_user(db_session, "front_desk", name="A front_desk")
    response = await api.get("/api/v1/auth/me", headers=persona_headers(user))

    assert response.json()["permissions"] == [
        "CREATE_PATIENT",
        "EDIT_DEMOGRAPHICS",
        "SCHEDULE_VISITS",
        "VIEW_DEMOGRAPHICS",
    ]
