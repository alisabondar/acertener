from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import httpx2
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.crypto import FieldCipher
from app.db.models import User, Visit
from app.demo.schedule import keep_schedule_current
from tests.factories import add_user, add_visit, create_patient, persona_headers

pytestmark = [pytest.mark.db, pytest.mark.anyio]

TZ = ZoneInfo("America/New_York")
TODAY = date(2026, 10, 19)


def _at(day: date, hour: int) -> datetime:
    return datetime.combine(day, time(hour), tzinfo=TZ)


async def _days(session: AsyncSession) -> list[tuple[date, int]]:
    visits = await session.scalars(select(Visit).order_by(Visit.scheduled_at))
    return [
        (v.scheduled_at.astimezone(TZ).date(), v.scheduled_at.astimezone(TZ).hour) for v in visits
    ]


@pytest.fixture
async def doctor(db_session: AsyncSession) -> User:
    return await add_user(db_session, "provider")


async def test_moves_the_latest_seeded_day_onto_today_keeping_clinic_hours(
    db_session: AsyncSession, field_cipher: FieldCipher, doctor: User
) -> None:
    patient = await create_patient(db_session, field_cipher)
    seeded_day = TODAY - timedelta(days=3)
    await add_visit(db_session, patient, doctor, _at(seeded_day, 9), "scheduled")
    await add_visit(db_session, patient, doctor, _at(seeded_day, 14), "checked_in")
    await add_visit(db_session, patient, doctor, _at(TODAY - timedelta(days=90), 10), "completed")

    moved = await keep_schedule_current(db_session, TODAY, TZ)

    assert moved == 2
    assert await _days(db_session) == [
        (TODAY - timedelta(days=90), 10),
        (TODAY, 9),
        (TODAY, 14),
    ]


async def test_leaves_a_day_that_already_has_visits_alone(
    db_session: AsyncSession, field_cipher: FieldCipher, doctor: User
) -> None:
    patient = await create_patient(db_session, field_cipher)
    await add_visit(db_session, patient, doctor, _at(TODAY - timedelta(days=1), 9), "scheduled")
    await add_visit(db_session, patient, doctor, _at(TODAY, 11), "scheduled")

    assert await keep_schedule_current(db_session, TODAY, TZ) == 0
    assert (TODAY - timedelta(days=1), 9) in await _days(db_session)


async def test_does_nothing_without_any_visits(db_session: AsyncSession) -> None:
    assert await keep_schedule_current(db_session, TODAY, TZ) == 0


async def test_my_day_in_demo_mode_always_has_todays_schedule(
    api: httpx2.AsyncClient,
    db_session: AsyncSession,
    field_cipher: FieldCipher,
    settings: Settings,
    doctor: User,
) -> None:
    tz = ZoneInfo(settings.practice_timezone)
    today = datetime.now(UTC).astimezone(tz).date()
    patient = await create_patient(db_session, field_cipher)
    yesterday_9am = datetime.combine(today - timedelta(days=1), time(9), tzinfo=tz)
    await add_visit(db_session, patient, doctor, yesterday_9am, "scheduled")

    response = await api.get("/api/v1/visits/today", headers=persona_headers(doctor))

    assert [item["status"] for item in response.json()["items"]] == ["scheduled"]
