"""Seed a small, deterministic, internally consistent dataset. Development only.

Run from backend/:  uv run python -m scripts.seed [--count 20] [--reset]
"""

import argparse
import asyncio
import random
import time as clock
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from decimal import Decimal
from zoneinfo import ZoneInfo

from faker import Faker
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.crypto import FernetFieldCipher, FieldCipher, load_or_create_keys
from app.db import create_engine
from app.db.models import (
    Allergy,
    Base,
    CareTeamMember,
    Condition,
    Note,
    Patient,
    User,
    Visit,
    Vital,
)
from app.db.types import set_field_cipher
from app.demo.personas import PERSONAS
from app.patients.queries import practice_today
from app.patients.repository import NewPatient, PatientRepository

SEED = 20261017
DEFAULT_COUNT = 10_000
BATCH_SIZE = 1_000
# Today's visits per persona provider (the nurse persona sees those of her care-team patients),
# one per hour from 9:00: a clinic day in progress, so My day shows every visit status.
TODAYS_STATUSES = [
    "completed",
    "completed",
    "completed",
    "no_show",
    "checked_in",
    "scheduled",
    "scheduled",
    "scheduled",
]
TODAYS_VISITS_EACH = len(TODAYS_STATUSES)
# Of inactive and deceased patients, the share an administrator has archived.
ARCHIVED_SHARE_OF_CLOSED = 0.2


# Besides the five personas: a small practice of 12 providers, 8 nurses and MAs, 4 front desk,
# and 1 admin.
EXTRA_STAFF = (
    [("provider", "MD")] * 6
    + [("provider", "NP")] * 2
    + [("provider", "PA")] * 2
    + [("nurse", "RN")] * 4
    + [("nurse", "MA")] * 3
    + [("front_desk", None)] * 3
)

VISIT_REASONS = [
    "Annual physical",
    "Blood pressure follow-up",
    "Medication review",
    "Cough and congestion",
    "Low back pain",
    "Diabetes check",
    "Anxiety follow-up",
]
NOTE_PLANS = [
    "Continue current medications and recheck in 3 months.",
    "Ordered labs; will call with results.",
    "Discussed diet and exercise; follow up as needed.",
    "Adjusted dose; monitor for side effects.",
]
ALLERGIES = [
    ("Penicillin", "Hives", "moderate"),
    ("Peanuts", "Anaphylaxis", "severe"),
    ("Sulfa drugs", "Rash", "mild"),
    ("Latex", "Itching", "mild"),
    ("Codeine", "Nausea", "mild"),
]
CONDITIONS = [
    ("E11.9", "Type 2 diabetes mellitus without complications"),
    ("I10", "Essential (primary) hypertension"),
    ("J45.909", "Unspecified asthma, uncomplicated"),
    ("E78.5", "Hyperlipidemia, unspecified"),
    ("F41.1", "Generalized anxiety disorder"),
    ("M54.50", "Low back pain, unspecified"),
    ("K21.9", "Gastro-esophageal reflux disease without esophagitis"),
]


@dataclass(frozen=True)
class SeedResult:
    skipped: bool
    patients: int = 0


def require_development(env: str) -> None:
    if env != "development":
        raise SystemExit(f"Refusing to seed: ENV is {env!r}, and seeding runs only in development.")


def _staff_id(email: str) -> uuid.UUID:
    """The same ID on every seed, so a persona chosen in an open tab survives a re-seed."""
    return uuid.uuid5(uuid.NAMESPACE_URL, f"mailto:{email}")


class _Seeder:
    """Builds rows in memory and writes them in FK-ordered stages, one batch at a time."""

    def __init__(self, session: AsyncSession, cipher: FieldCipher, today: date, tz: tzinfo) -> None:
        self.session = session
        self.repo = PatientRepository(session, cipher)
        self.today = today
        self.tz = tz
        # Reproducible synthetic data, not security: predictability is the point.
        self.rng = random.Random(SEED)  # noqa: S311
        self.fake = Faker()
        self.fake.seed_instance(SEED)
        # Rows waiting to be written, by stage: each stage only references earlier ones.
        self.stages: list[list[Base]] = [[], [], []]

    def _panel_mix(self) -> tuple[list[int], str]:
        """Visit history (days ago) and status for a typical primary-care panel."""
        roll = self.rng.random()
        if roll < 0.01:
            return self._visits(200, 2000), "deceased"
        if roll < 0.06:
            return self._visits(1100, 3000), "inactive"
        if roll < 0.09:
            # Still active on paper but unseen for 3+ years: the list suggests inactivity.
            return self._visits(1100, 1800), "active"
        return self._visits(14, 900), "active"

    def _visits(self, newest: int, oldest: int) -> list[int]:
        return sorted(self.rng.sample(range(newest, oldest), k=self.rng.randint(1, 4)))

    def _uuid(self) -> uuid.UUID:
        return uuid.UUID(int=self.rng.getrandbits(128), version=4)

    def _at(self, day: date, hour: int, minute: int = 0) -> datetime:
        """A clinic-hours time on `day`, in the practice's timezone."""
        return datetime.combine(day, time(hour, minute), tzinfo=self.tz)

    async def staff(self) -> None:
        people = [
            User(
                id=_staff_id(p.email),
                name=p.name,
                email=p.email,
                role=p.role,
                credential=p.credential,
            )
            for p in PERSONAS
        ]
        for n, (role, credential) in enumerate(EXTRA_STAFF, start=1):
            people.append(
                User(
                    id=_staff_id(f"staff{n}@demo.clinic"),
                    name=self.fake.name(),
                    email=f"staff{n}@demo.clinic",
                    role=role,
                    credential=credential,
                )
            )
        self.session.add_all(people)
        await self.session.flush()
        by_email = {u.email: u for u in people}
        self.chen, self.rivera = by_email["chen@demo.clinic"], by_email["rivera@demo.clinic"]
        self.okafor = by_email["okafor@demo.clinic"]
        self.admin = by_email["admin@demo.clinic"]
        extra = people[len(PERSONAS) :]
        # Personas get most patients so their "My patients" and "My day" views are full.
        self.primary_rotation = [self.chen, self.rivera, self.chen, self.rivera] + [
            u for u in extra if u.role == "provider"
        ]
        self.other_nurses = [u for u in extra if u.role == "nurse"]
        self.todays_visits = {self.chen.id: 0, self.rivera.id: 0}

    def patient(self, i: int, count: int) -> None:
        age = self.rng.randint(1, 95)
        dob = self.today - timedelta(days=age * 365 + self.rng.randint(0, 364))
        patient, prefixes = self.repo.build(
            NewPatient(
                first_name=self.fake.first_name(),
                last_name=self.fake.last_name(),
                mrn=f"MRN-{100000 + i}",
                dob=dob,
                gender=self.rng.choice(["female", "male", "nonbinary"]),
                phone=self.fake.numerify("555-###-####"),
                email=self.fake.safe_email(),
                address_line1=self.fake.street_address(),
                city=self.fake.city(),
                state=self.fake.state_abbr(),
                postal_code=self.fake.zipcode(),
            ),
            self._uuid(),
        )
        primary = self.primary_rotation[i % len(self.primary_rotation)]
        nurses = [self.okafor] if i % 2 == 0 else []
        nurses += self.rng.sample(self.other_nurses, k=1 if nurses else self.rng.randint(1, 2))
        self.stages[1] += prefixes
        self.stages[1].append(
            CareTeamMember(patient_id=patient.id, user_id=primary.id, role="primary_provider")
        )
        self.stages[1] += [
            CareTeamMember(patient_id=patient.id, user_id=n.id, role="nurse") for n in nurses
        ]

        # The last three patients cover the status mix: deceased, inactive, and long unseen.
        special = count - i
        if special == 1:
            visit_days, patient.status = [730], "deceased"
        elif special == 2:
            visit_days, patient.status = [1825], "inactive"
        elif special == 3:
            visit_days, patient.status = [1460], "active"
        else:
            visit_days, patient.status = self._panel_mix()
        if patient.status != "active" and self.rng.random() < ARCHIVED_SHARE_OF_CLOSED:
            patient.archived_at = datetime.combine(
                self.today - timedelta(days=self.rng.randint(30, 365)), time(9), tzinfo=self.tz
            )
            patient.archived_by = self.admin.id

        completed = [
            self._past_visit(
                patient,
                primary,
                nurses[0],
                self.today - timedelta(days=d),
                # The most recent visit is always completed, so every patient has a last visit.
                allow_no_show=d != min(visit_days),
            )
            for d in visit_days
        ]
        # A realistic day: a handful of today's visits for each persona provider.
        booked = self.todays_visits.get(primary.id)
        if (
            booked is not None
            and booked < TODAYS_VISITS_EACH
            and patient.status == "active"
            and min(visit_days) < 900
        ):
            self.todays_visits[primary.id] = booked + 1
            when = self._at(self.today, 9 + booked, 30 * (primary is self.rivera))
            visit = Visit(
                id=self._uuid(),
                patient_id=patient.id,
                provider_id=primary.id,
                scheduled_at=when,
                status=TODAYS_STATUSES[booked],
                reason=self.rng.choice(VISIT_REASONS),
            )
            self.stages[1].append(visit)
            if visit.status == "completed":
                # Seen this morning: vitals were taken, and today is now the last visit.
                self._vitals(patient, visit, nurses[0], when)
                completed.append(when)
        for substance, reaction, severity in self.rng.sample(ALLERGIES, k=self.rng.randint(0, 2)):
            self.stages[2].append(
                Allergy(
                    patient_id=patient.id,
                    substance=substance,
                    reaction=reaction,
                    severity=severity,
                    recorded_by=primary.id,
                )
            )
        for code, name in self.rng.sample(CONDITIONS, k=self.rng.randint(0, 3)):
            self.stages[2].append(
                Condition(patient_id=patient.id, icd10_code=code, name=name, recorded_by=primary.id)
            )
        patient.last_visit_at = max((v for v in completed if v is not None), default=None)
        self.stages[0].append(patient)

    def _past_visit(
        self, patient: Patient, provider: User, nurse: User, day: date, *, allow_no_show: bool
    ) -> datetime | None:
        when = self._at(day, self.rng.randint(8, 16))
        no_show = allow_no_show and self.rng.random() < 0.1
        reason = self.rng.choice(VISIT_REASONS)
        visit = Visit(
            id=self._uuid(),
            patient_id=patient.id,
            provider_id=provider.id,
            scheduled_at=when,
            status="no_show" if no_show else "completed",
            reason=reason,
        )
        self.stages[1].append(visit)
        if no_show:
            return None
        self._vitals(patient, visit, nurse, when)
        # Up to two notes per visit (the provider's and the nurse's), so 0 to 8 per patient.
        for author, chance in ((provider, 0.7), (nurse, 0.3)):
            if self.rng.random() < chance:
                self.stages[2].append(
                    Note(
                        patient_id=patient.id,
                        author_id=author.id,
                        encounter_at=when,
                        content=f"{reason}. Vitals reviewed. {self.rng.choice(NOTE_PLANS)}",
                        status="final",
                        finalized_at=when + timedelta(hours=2),
                    )
                )
        return when

    def _vitals(self, patient: Patient, visit: Visit, nurse: User, when: datetime) -> None:
        self.stages[2].append(
            Vital(
                patient_id=patient.id,
                visit_id=visit.id,
                recorded_by=nurse.id,
                taken_at=when,
                bp_systolic=self.rng.randint(105, 150),
                bp_diastolic=self.rng.randint(65, 95),
                heart_rate=self.rng.randint(58, 98),
                respiratory_rate=self.rng.randint(12, 20),
                spo2=self.rng.randint(94, 100),
                temperature_c=Decimal(self.rng.randint(361, 376)) / 10,
                weight_kg=Decimal(self.rng.randint(450, 1100)) / 10,
                height_cm=Decimal(self.rng.randint(1500, 1950)) / 10,
            )
        )

    async def write_batch(self) -> None:
        for stage in self.stages:
            self.session.add_all(stage)
            await self.session.flush()
            for row in stage:
                self.session.expunge(row)  # keep memory flat across a 10k+ load
            stage.clear()


async def seed(
    session: AsyncSession,
    cipher: FieldCipher,
    *,
    count: int = DEFAULT_COUNT,
    today: date,
    tz: tzinfo = UTC,
    progress: Callable[[int, int], None] | None = None,
) -> SeedResult:
    """Insert the dataset unless patients already exist. The caller commits."""
    if await session.scalar(select(func.count()).select_from(Patient)):
        return SeedResult(skipped=True)
    seeder = _Seeder(session, cipher, today, tz)
    await seeder.staff()
    for i in range(count):
        seeder.patient(i, count)
        if (i + 1) % BATCH_SIZE == 0 or i + 1 == count:
            await seeder.write_batch()
            if progress is not None:
                progress(i + 1, count)
    return SeedResult(skipped=False, patients=count)


async def reset(session: AsyncSession) -> None:
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    await session.execute(text(f"TRUNCATE {tables} CASCADE"))


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument("--reset", action="store_true", help="delete all data first")
    args = parser.parse_args()

    settings = get_settings()
    require_development(settings.env)
    keys = load_or_create_keys(settings.keys_dir)
    cipher = FernetFieldCipher(keys.field_keys, keys.fingerprint_key)
    set_field_cipher(cipher)
    tz = ZoneInfo(settings.practice_timezone)
    started = clock.monotonic()

    def progress(done: int, total: int) -> None:
        elapsed = clock.monotonic() - started
        remaining = elapsed / done * (total - done)
        print(f"  {done:>6}/{total} patients  {elapsed:5.1f}s elapsed  ~{remaining:4.0f}s left")

    engine = create_engine(settings.database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            if args.reset:
                await reset(session)
            result = await seed(
                session,
                cipher,
                count=args.count,
                today=practice_today(datetime.now(UTC), tz),
                tz=tz,
                progress=progress,
            )
            await session.commit()
    finally:
        await engine.dispose()
    if result.skipped:
        print("Already seeded; use --reset to start over.")
    else:
        print(f"Seeded {result.patients} patients in {clock.monotonic() - started:.1f}s.")


if __name__ == "__main__":
    asyncio.run(main())
