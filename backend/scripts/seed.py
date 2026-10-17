"""Seed a small, deterministic, internally consistent dataset. Development only.

Run from backend/:  uv run python -m scripts.seed [--count 20] [--reset]
"""

import argparse
import asyncio
import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

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
from app.patients.repository import NewPatient, PatientRepository

SEED = 20261017
DEFAULT_COUNT = 20


EXTRA_STAFF = [("provider", "MD"), ("provider", "PA"), ("nurse", "RN"), ("nurse", "MA")]

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


def _at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=UTC)


class _Seeder:
    def __init__(self, session: AsyncSession, cipher: FieldCipher, today: date) -> None:
        self.session = session
        self.repo = PatientRepository(session, cipher)
        self.today = today
        # Reproducible synthetic data, not security: predictability is the point.
        self.rng = random.Random(SEED)  # noqa: S311
        self.fake = Faker()
        self.fake.seed_instance(SEED)

    async def staff(self) -> None:
        people = [
            User(name=p.name, email=p.email, role=p.role, credential=p.credential) for p in PERSONAS
        ]
        for n, (role, credential) in enumerate(EXTRA_STAFF, start=1):
            people.append(
                User(
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
        extra = people[len(PERSONAS) :]
        # Personas get most patients so their "My patients" and "My day" views are full.
        self.primary_rotation = [self.chen, self.rivera, self.chen, self.rivera] + [
            u for u in extra if u.role == "provider"
        ]
        self.other_nurses = [u for u in extra if u.role == "nurse"]

    async def patient(self, i: int, count: int) -> None:
        age = self.rng.randint(1, 95)
        dob = self.today - timedelta(days=age * 365 + self.rng.randint(0, 364))
        patient = await self.repo.create(
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
            )
        )
        primary = self.primary_rotation[i % len(self.primary_rotation)]
        nurses = [self.okafor] if i % 2 == 0 else []
        nurses += self.rng.sample(self.other_nurses, k=1 if nurses else self.rng.randint(1, 2))
        self.session.add(
            CareTeamMember(patient_id=patient.id, user_id=primary.id, role="primary_provider")
        )
        self.session.add_all(
            CareTeamMember(patient_id=patient.id, user_id=n.id, role="nurse") for n in nurses
        )

        # The last three patients cover the status mix: deceased, inactive, and long unseen.
        special = count - i
        if special == 1:
            visit_days, status = [730], "deceased"
        elif special == 2:
            visit_days, status = [1825], "inactive"
        elif special == 3:
            visit_days, status = [1460], "active"
        else:
            visit_days = sorted(self.rng.sample(range(14, 900), k=self.rng.randint(1, 4)))
            status = "active"

        completed = [
            await self._past_visit(
                patient,
                primary,
                nurses[0],
                self.today - timedelta(days=d),
                # The most recent visit is always completed, so every patient has a last visit.
                allow_no_show=d != min(visit_days),
            )
            for d in visit_days
        ]
        if primary in (self.chen, self.rivera) and i < count * 3 // 5:
            self.session.add(
                Visit(
                    patient_id=patient.id,
                    provider_id=primary.id,
                    scheduled_at=_at(self.today, 9 + (i // 2) % 8, 30 * (i % 2)),
                    status=self.rng.choice(["scheduled", "scheduled", "checked_in"]),
                    reason=self.rng.choice(VISIT_REASONS),
                )
            )
        for substance, reaction, severity in self.rng.sample(ALLERGIES, k=self.rng.randint(0, 2)):
            self.session.add(
                Allergy(
                    patient_id=patient.id,
                    substance=substance,
                    reaction=reaction,
                    severity=severity,
                    recorded_by=primary.id,
                )
            )
        for code, name in self.rng.sample(CONDITIONS, k=self.rng.randint(0, 3)):
            self.session.add(
                Condition(patient_id=patient.id, icd10_code=code, name=name, recorded_by=primary.id)
            )
        last_visit = max((v for v in completed if v is not None), default=None)
        await self.repo.update(patient.id, status=status, last_visit_at=last_visit)

    async def _past_visit(
        self, patient: Patient, provider: User, nurse: User, day: date, *, allow_no_show: bool
    ) -> datetime | None:
        when = _at(day, self.rng.randint(8, 16))
        no_show = allow_no_show and self.rng.random() < 0.1
        reason = self.rng.choice(VISIT_REASONS)
        visit = Visit(
            patient_id=patient.id,
            provider_id=provider.id,
            scheduled_at=when,
            status="no_show" if no_show else "completed",
            reason=reason,
        )
        self.session.add(visit)
        if no_show:
            return None
        await self.session.flush()
        self.session.add(
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
        if self.rng.random() < 0.7:
            author = self.rng.choice([provider, nurse])
            self.session.add(
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


async def seed(
    session: AsyncSession, cipher: FieldCipher, *, count: int = DEFAULT_COUNT, today: date
) -> SeedResult:
    """Insert the dataset unless patients already exist. The caller commits."""
    if await session.scalar(select(func.count()).select_from(Patient)):
        return SeedResult(skipped=True)
    seeder = _Seeder(session, cipher, today)
    await seeder.staff()
    for i in range(count):
        await seeder.patient(i, count)
    await session.flush()
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
    engine = create_engine(settings.database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            if args.reset:
                await reset(session)
            result = await seed(session, cipher, count=args.count, today=date.today())
            await session.commit()
    finally:
        await engine.dispose()
    print(
        "Already seeded; use --reset to start over."
        if result.skipped
        else f"Seeded {result.patients} patients."
    )


if __name__ == "__main__":
    asyncio.run(main())
