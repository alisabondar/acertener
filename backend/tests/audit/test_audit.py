import uuid
from typing import Annotated

import httpx2
import pytest
from fastapi import Depends, FastAPI
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import Audit, AuditAction, AuditEntry, get_audit
from app.auth.permissions import Permission, require
from app.db.models import AuditLog, User
from tests.factories import make_audit, make_user

pytestmark = [pytest.mark.db, pytest.mark.anyio]

PATIENT_ID = uuid.uuid4()


@pytest.fixture(autouse=True)
def routes(app: FastAPI) -> None:
    @app.get("/test/chart")
    async def chart(audit: Annotated[Audit, Depends(get_audit)]) -> str:
        audit.record_read(AuditEntry(AuditAction.VIEW, "patient", PATIENT_ID, PATIENT_ID))
        return "ok"

    @app.get("/test/clinical")
    async def clinical(user: Annotated[User, Depends(require(Permission.VIEW_CLINICAL))]) -> str:
        return "ok"


async def _persona(session: AsyncSession, role: str) -> User:
    user = make_user(role=role, credential=None)
    session.add(user)
    await session.flush()
    return user


async def _entries(session: AsyncSession) -> list[AuditLog]:
    return list(await session.scalars(select(AuditLog).order_by(AuditLog.id)))


async def test_reads_are_recorded_after_the_response(
    api: httpx2.AsyncClient, db_session: AsyncSession
) -> None:
    nurse = await _persona(db_session, "nurse")

    response = await api.get("/test/chart", headers={"X-Persona": str(nurse.id)})

    [entry] = await _entries(db_session)
    assert (entry.actor_id, entry.via_demo_persona) == (nurse.id, True)
    assert (entry.action, entry.entity, entry.patient_id) == ("view", "patient", PATIENT_ID)
    assert entry.request_id == response.headers["X-Request-ID"]


async def test_denied_access_is_recorded(api: httpx2.AsyncClient, db_session: AsyncSession) -> None:
    front_desk = await _persona(db_session, "front_desk")

    response = await api.get("/test/clinical", headers={"X-Persona": str(front_desk.id)})

    assert response.status_code == 403
    [entry] = await _entries(db_session)
    assert (entry.actor_id, entry.action, entry.entity) == (
        front_desk.id,
        "access_denied",
        "VIEW_CLINICAL",
    )


async def test_changes_share_the_callers_transaction(db_session: AsyncSession) -> None:
    provider = await _persona(db_session, "provider")
    audit = await make_audit(db_session, provider)

    savepoint = await db_session.begin_nested()
    await audit.record_change(
        AuditEntry(AuditAction.UPDATE, "patient", PATIENT_ID, PATIENT_ID, {"city": ("A", "B")})
    )
    await savepoint.rollback()

    assert await _entries(db_session) == []


@pytest.mark.parametrize(
    "statement", ["UPDATE audit_log SET action = 'x'", "DELETE FROM audit_log"]
)
async def test_audit_log_is_append_only(db_session: AsyncSession, statement: str) -> None:
    provider = await _persona(db_session, "provider")
    audit = await make_audit(db_session, provider)
    await audit.record_change(AuditEntry(AuditAction.VIEW, "patient", PATIENT_ID, PATIENT_ID))

    with pytest.raises(DBAPIError, match="append-only"):
        async with db_session.begin_nested():
            await db_session.execute(text(statement))
