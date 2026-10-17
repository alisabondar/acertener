from collections.abc import AsyncIterator
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx2
import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import FieldCipher
from app.db.models import AuditLog, User
from app.patients.queries import practice_today
from app.patients.repository import PatientRepository
from tests.factories import add_to_care_team, add_user, add_visit, create_patient, persona_headers

pytestmark = [pytest.mark.db, pytest.mark.anyio]

PRACTICE_TZ = ZoneInfo("America/New_York")
NOW = datetime.now(UTC)


@pytest.fixture
async def me(db_session: AsyncSession) -> User:
    return await add_user(db_session, "provider")


@pytest.fixture
async def practice(db_session: AsyncSession, field_cipher: FieldCipher, me: User) -> None:
    """Two active (one with a late-evening visit today, practice time), one inactive,
    one deceased, and one archived patient. Only the first two are on my care team."""
    repo = PatientRepository(db_session, field_cipher)
    late_tonight = datetime.combine(practice_today(NOW, PRACTICE_TZ), time(23, 30), PRACTICE_TZ)
    seen_today = await create_patient(db_session, field_cipher)
    await add_visit(db_session, seen_today, me, late_tonight, "scheduled")
    await add_to_care_team(db_session, seen_today, me)
    await add_to_care_team(db_session, await create_patient(db_session, field_cipher), me)
    for status in ("inactive", "deceased"):
        patient = await create_patient(db_session, field_cipher)
        await repo.update(patient.id, status=status)
    archived = await create_patient(db_session, field_cipher)
    await repo.update(archived.id, archived_at=NOW - timedelta(days=1), archive_reason="other")


async def _counts(api: httpx2.AsyncClient, me: User, scope: str) -> Any:
    response = await api.get(
        "/api/v1/patients/filter-counts", params={"scope": scope}, headers=persona_headers(me)
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _total(api: httpx2.AsyncClient, me: User, **params: Any) -> int:
    response = await api.get("/api/v1/patients", params=params, headers=persona_headers(me))
    return int(response.json()["total"])


@pytest.mark.usefixtures("practice")
@pytest.mark.parametrize("scope", ["all", "my"])
async def test_counts_match_what_each_chip_lists(
    api: httpx2.AsyncClient, me: User, scope: str
) -> None:
    counts = await _counts(api, me, scope)

    assert counts["today_visits"] == await _total(api, me, scope=scope, filter="today_visits")
    for status, count in counts["status"].items():
        assert count == await _total(api, me, scope=scope, status=status)
    everything = await _total(api, me, scope=scope, include_archived=True)
    assert counts["archived"] == everything - await _total(api, me, scope=scope)


@pytest.mark.usefixtures("practice")
async def test_counts_for_the_seeded_practice(api: httpx2.AsyncClient, me: User) -> None:
    assert await _counts(api, me, "all") == {
        "today_visits": 1,
        "status": {"active": 2, "inactive": 1, "deceased": 1},
        "archived": 1,
    }
    assert await _counts(api, me, "my") == {
        "today_visits": 1,
        "status": {"active": 2, "inactive": 0, "deceased": 0},
        "archived": 0,
    }


@pytest.fixture
async def patient_queries(db_session: AsyncSession) -> AsyncIterator[list[str]]:
    statements: list[str] = []
    sync_conn = (await db_session.connection()).sync_connection
    assert sync_conn is not None

    def record(_conn: object, _cursor: object, statement: str, *_: object) -> None:
        if statement.lstrip().upper().startswith("SELECT") and "FROM patients" in statement:
            statements.append(statement)

    event.listen(sync_conn, "before_cursor_execute", record)
    yield statements
    event.remove(sync_conn, "before_cursor_execute", record)


@pytest.mark.usefixtures("practice")
async def test_all_counts_come_from_one_query(
    api: httpx2.AsyncClient, me: User, patient_queries: list[str]
) -> None:
    await _counts(api, me, "all")

    assert len(patient_queries) == 1


@pytest.mark.parametrize("role", ["provider", "nurse", "front_desk", "admin"])
async def test_every_role_can_read_counts_and_it_is_audited(
    api: httpx2.AsyncClient, db_session: AsyncSession, role: str
) -> None:
    viewer = await add_user(db_session, role)

    await _counts(api, viewer, "all")

    entities = [e.entity for e in await db_session.scalars(select(AuditLog))]
    assert entities == ["patient_counts"]
