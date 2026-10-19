from datetime import UTC, date, datetime, time
from typing import Any, cast
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import FieldCipher
from app.db.models import CareTeamMember, Note, Patient, User, Visit, Vital
from app.demo.personas import PERSONAS
from app.schemas.patients import Scope
from app.visits.queries import todays_visits
from scripts.seed import _Seeder, require_development, seed

TODAY = date(2026, 10, 17)
SMALL = 20  # the default is 10,000; tests stay small


async def _snapshot(session: AsyncSession) -> dict[str, list[tuple[Any, ...]]]:
    """Seeded content, including patient ids (the seed generates them deterministically)."""
    mrn = {p.id: p.mrn for p in await session.scalars(select(Patient))}
    email = {u.id: u.email for u in await session.scalars(select(User))}
    patients = [
        (p.id, p.mrn, p.first_name, p.last_name, p.dob, p.gender, p.status, p.last_visit_at)
        for p in await session.scalars(select(Patient))
    ]
    visits = [
        (mrn[v.patient_id], email[v.provider_id], v.scheduled_at, v.status, v.reason)
        for v in await session.scalars(select(Visit))
    ]
    notes = [
        (mrn[n.patient_id], email[n.author_id], n.encounter_at, n.content)
        for n in await session.scalars(select(Note))
    ]
    return {"patients": sorted(patients), "visits": sorted(visits), "notes": sorted(notes)}


@pytest.mark.parametrize("env", ["production", "test"])
def test_seed_refuses_outside_development(env: str) -> None:
    with pytest.raises(SystemExit, match="development"):
        require_development(env)


@pytest.mark.db
@pytest.mark.anyio
async def test_reseeding_gives_identical_results(
    db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    snapshots = []
    for _ in range(2):
        savepoint = await db_session.begin_nested()
        await seed(db_session, field_cipher, count=SMALL, today=TODAY)
        snapshots.append(await _snapshot(db_session))
        await savepoint.rollback()

    assert snapshots[0] == snapshots[1]
    assert len(snapshots[0]["patients"]) == SMALL


@pytest.mark.db
@pytest.mark.anyio
async def test_personas_are_seeded(db_session: AsyncSession, field_cipher: FieldCipher) -> None:
    await seed(db_session, field_cipher, count=SMALL, today=TODAY)

    users = {u.email: u for u in await db_session.scalars(select(User))}

    for persona in PERSONAS:
        assert (users[persona.email].role, users[persona.email].credential) == (
            persona.role,
            persona.credential,
        )
    assert "developer@demo.clinic" not in users


@pytest.mark.db
@pytest.mark.anyio
async def test_staff_keep_their_ids_across_reseeds(
    db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    runs = []
    for _ in range(2):
        savepoint = await db_session.begin_nested()
        await seed(db_session, field_cipher, count=SMALL, today=TODAY)
        runs.append({u.email: u.id for u in await db_session.scalars(select(User))})
        await savepoint.rollback()

    assert runs[0] == runs[1]


@pytest.mark.db
@pytest.mark.anyio
async def test_seeded_data_is_clinically_consistent(
    db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    await seed(db_session, field_cipher, count=SMALL, today=TODAY)

    primaries = await db_session.execute(
        select(CareTeamMember.patient_id, func.count())
        .where(CareTeamMember.role == "primary_provider", CareTeamMember.end_date.is_(None))
        .group_by(CareTeamMember.patient_id)
    )
    assert sorted(n for _, n in primaries) == [1] * SMALL

    vitals_on_open_visits = await db_session.scalar(
        select(func.count())
        .select_from(Vital)
        .join(Visit, Vital.visit_id == Visit.id)
        .where(Visit.status != "completed")
    )
    assert vitals_on_open_visits == 0

    start = datetime.combine(TODAY, time.min, tzinfo=UTC)
    end = datetime.combine(TODAY, time.max, tzinfo=UTC)
    for persona in [p for p in PERSONAS if p.role == "provider"]:
        todays = await db_session.scalar(
            select(func.count())
            .select_from(Visit)
            .join(User, Visit.provider_id == User.id)
            .where(User.email == persona.email, Visit.scheduled_at.between(start, end))
        )
        assert todays is not None
        assert todays >= 2, persona.email

    statuses = set(await db_session.scalars(select(Patient.status)))
    assert {"active", "inactive", "deceased"} <= statuses
    three_years_ago = datetime.combine(TODAY.replace(year=TODAY.year - 3), time.min, tzinfo=UTC)
    long_unseen = await db_session.scalar(
        select(func.count())
        .select_from(Patient)
        .where(Patient.status == "active", Patient.last_visit_at < three_years_ago)
    )
    assert long_unseen is not None
    assert long_unseen >= 1


@pytest.mark.db
@pytest.mark.anyio
async def test_seeding_twice_adds_nothing(
    db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    await seed(db_session, field_cipher, count=SMALL, today=TODAY)

    second = await seed(db_session, field_cipher, count=SMALL, today=TODAY)

    assert second.skipped
    assert await db_session.scalar(select(func.count()).select_from(Patient)) == SMALL


@pytest.mark.db
@pytest.mark.anyio
async def test_seed_has_a_realistic_status_mix(
    db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    count = 1000
    await seed(db_session, field_cipher, count=count, today=TODAY)
    patients = list(await db_session.scalars(select(Patient)))
    three_years_ago = datetime.combine(TODAY.replace(year=TODAY.year - 3), time(), tzinfo=UTC)

    def share(predicate: Any) -> float:
        return sum(1 for p in patients if predicate(p)) / count

    # The spec's mix: about 5% inactive, about 1% deceased, and a few long-unseen actives.
    assert 0.003 <= share(lambda p: p.status == "deceased") <= 0.02
    assert 0.03 <= share(lambda p: p.status == "inactive") <= 0.07
    assert (
        0.01 <= share(lambda p: p.status == "active" and p.last_visit_at < three_years_ago) <= 0.05
    )
    archived = [p for p in patients if p.archived_at is not None]
    assert archived
    assert all(p.status != "active" for p in archived)


@pytest.mark.db
@pytest.mark.anyio
async def test_seed_works_on_a_leap_day(
    db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    result = await seed(db_session, field_cipher, count=SMALL, today=date(2028, 2, 29))

    assert result.patients == SMALL


@pytest.mark.db
@pytest.mark.anyio
@pytest.mark.parametrize("count", range(4, 16))
async def test_status_mix_patients_always_have_a_last_visit(
    db_session: AsyncSession, field_cipher: FieldCipher, count: int
) -> None:
    await seed(db_session, field_cipher, count=count, today=TODAY)

    unseen = await db_session.scalars(select(Patient.mrn).where(Patient.last_visit_at.is_(None)))

    assert list(unseen) == []


@pytest.mark.db
@pytest.mark.anyio
async def test_staff_match_a_small_practice(
    db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    await seed(db_session, field_cipher, count=SMALL, today=TODAY)

    roles = dict(
        (await db_session.execute(select(User.role, func.count()).group_by(User.role))).all()
    )

    assert roles == {"provider": 12, "nurse": 8, "front_desk": 4, "admin": 1}


@pytest.mark.db
@pytest.mark.anyio
async def test_each_clinical_persona_has_several_of_todays_visits(
    db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    tz = ZoneInfo("America/New_York")
    await seed(db_session, field_cipher, count=200, today=TODAY, tz=tz)
    users = {u.email: u for u in await db_session.scalars(select(User))}

    for email in ("chen@demo.clinic", "rivera@demo.clinic", "okafor@demo.clinic"):
        visits = await todays_visits(db_session, users[email], Scope.MY, TODAY, tz)
        assert len(visits) >= 3, email


@pytest.mark.db
@pytest.mark.anyio
async def test_patients_have_zero_to_eight_final_notes(
    db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    await seed(db_session, field_cipher, count=200, today=TODAY)

    per_patient = (
        await db_session.scalars(
            select(func.count(Note.id)).select_from(Patient).outerjoin(Note).group_by(Patient.id)
        )
    ).all()

    assert min(per_patient) == 0
    assert 4 < max(per_patient) <= 8


class _NoDatabase:
    """Lets the seeder build rows in memory without writing them anywhere."""

    def add_all(self, rows: object) -> None:
        pass

    async def flush(self) -> None:
        pass


@pytest.mark.anyio
async def test_every_patient_gets_an_explicit_status_before_archiving_is_decided(
    field_cipher: FieldCipher,
) -> None:
    """A status left to the database default reads as None here, which isn't "active"."""
    seeder = _Seeder(cast(AsyncSession, _NoDatabase()), field_cipher, TODAY, UTC)
    await seeder.staff()
    for i in range(1000):
        seeder.patient(i, 1000)

    patients = [row for row in seeder.stages[0] if isinstance(row, Patient)]
    assert all(p.status in ("active", "inactive", "deceased") for p in patients)


@pytest.mark.db
@pytest.mark.anyio
async def test_each_provider_persona_has_every_visit_status_today(
    db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    tz = ZoneInfo("America/New_York")
    await seed(db_session, field_cipher, count=200, today=TODAY, tz=tz)
    users = {u.email: u for u in await db_session.scalars(select(User))}

    for email in ("chen@demo.clinic", "rivera@demo.clinic"):
        visits = await todays_visits(db_session, users[email], Scope.MY, TODAY, tz)
        statuses = {v.visit.status for v in visits if v.visit.provider_id == users[email].id}
        assert statuses == {"completed", "no_show", "checked_in", "scheduled"}, email
