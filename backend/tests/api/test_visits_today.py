from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx2
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.crypto import FieldCipher
from app.db.models import AuditLog, User
from tests.factories import (
    add_to_care_team,
    add_user,
    add_visit,
    create_patient,
    persona_headers,
)

pytestmark = [pytest.mark.db, pytest.mark.anyio]


def _at(settings: Settings, hour: int, days: int = 0) -> datetime:
    """A time on the practice's calendar day, `days` from today."""
    tz = ZoneInfo(settings.practice_timezone)
    today = datetime.now(UTC).astimezone(tz).date() + timedelta(days=days)
    return datetime.combine(today, time(hour), tzinfo=tz)


async def _today(api: httpx2.AsyncClient, user: User, **params: str) -> list[dict[str, Any]]:
    response = await api.get("/api/v1/visits/today", params=params, headers=persona_headers(user))
    assert response.status_code == 200, response.text
    items: list[dict[str, Any]] = response.json()["items"]
    return items


async def test_lists_todays_visits_in_time_order(
    api: httpx2.AsyncClient,
    db_session: AsyncSession,
    field_cipher: FieldCipher,
    settings: Settings,
) -> None:
    doctor = await add_user(db_session, "provider", name="Dr. Lee")
    early = await create_patient(db_session, field_cipher, last_name="Early")
    late = await create_patient(db_session, field_cipher, last_name="Late")
    await add_visit(db_session, late, doctor, _at(settings, 15), "scheduled", "Follow-up")
    await add_visit(db_session, early, doctor, _at(settings, 9), "checked_in", "Cough")
    await add_visit(db_session, early, doctor, _at(settings, 9, days=-1), "completed")
    await add_visit(db_session, early, doctor, _at(settings, 9, days=1), "scheduled")

    items: list[dict[str, Any]] = await _today(api, doctor)

    assert [(i["patient"]["last_name"], i["status"]) for i in items] == [
        ("Early", "checked_in"),
        ("Late", "scheduled"),
    ]
    first = items[0]
    assert first["reason"] == "Cough"
    assert first["provider_name"] == "Dr. Lee"
    assert set(first["patient"]) >= {"id", "first_name", "last_name", "dob", "age", "mrn"}


async def test_my_visits_are_mine_as_provider_or_through_my_care_team(
    api: httpx2.AsyncClient,
    db_session: AsyncSession,
    field_cipher: FieldCipher,
    settings: Settings,
) -> None:
    doctor = await add_user(db_session, "provider")
    other_doctor = await add_user(db_session, "provider")
    nurse = await add_user(db_session, "nurse")
    mine = await create_patient(db_session, field_cipher, last_name="Mine")
    teamed = await create_patient(db_session, field_cipher, last_name="Teamed")
    await add_to_care_team(db_session, teamed, nurse)
    await add_visit(db_session, mine, doctor, _at(settings, 10), "scheduled")
    await add_visit(db_session, teamed, other_doctor, _at(settings, 11), "scheduled")

    def names(items: list[dict[str, Any]]) -> list[Any]:
        return [i["patient"]["last_name"] for i in items]

    assert names(await _today(api, doctor)) == ["Mine"]
    assert names(await _today(api, nurse)) == ["Teamed"]
    assert names(await _today(api, doctor, scope="all")) == ["Mine", "Teamed"]


async def test_front_desk_sees_the_schedule_without_clinical_reasons(
    api: httpx2.AsyncClient,
    db_session: AsyncSession,
    field_cipher: FieldCipher,
    settings: Settings,
) -> None:
    doctor = await add_user(db_session, "provider")
    desk = await add_user(db_session, "front_desk")
    patient = await create_patient(db_session, field_cipher)
    await add_visit(db_session, patient, doctor, _at(settings, 10), "scheduled", "Chest pain")

    [item] = await _today(api, desk, scope="all")

    assert item["reason"] is None


async def test_admin_has_no_schedule(api: httpx2.AsyncClient, db_session: AsyncSession) -> None:
    admin = await add_user(db_session, "admin")

    response = await api.get("/api/v1/visits/today", headers=persona_headers(admin))

    assert response.status_code == 403


async def test_viewing_the_schedule_is_audited(
    api: httpx2.AsyncClient, db_session: AsyncSession
) -> None:
    doctor = await add_user(db_session, "provider")

    await _today(api, doctor)

    entries = list(await db_session.scalars(select(AuditLog)))
    assert [(e.action, e.entity, e.actor_id) for e in entries] == [
        ("view", "todays_visits", doctor.id)
    ]
