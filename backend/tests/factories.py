import itertools
from datetime import date, datetime
from typing import Any

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.audit import Audit
from app.crypto import FieldCipher
from app.db.models import CareTeamMember, Patient, User, Visit
from app.patients.repository import NewPatient, PatientRepository

_ids = itertools.count(1)


def make_user(**overrides: Any) -> User:
    n = next(_ids)
    fields: dict[str, Any] = {
        "name": f"Test User {n}",
        "email": f"user{n}@demo.clinic",
        "role": "provider",
        "credential": "MD",
    }
    fields.update(overrides)
    return User(**fields)


async def create_patient(session: AsyncSession, cipher: FieldCipher, **overrides: Any) -> Patient:
    fields: dict[str, Any] = {
        "first_name": "Ada",
        "last_name": "Smith",
        "mrn": f"MRN-{next(_ids):05d}",
        "dob": date(1990, 1, 31),
    }
    fields.update(overrides)
    return await PatientRepository(session, cipher).create(NewPatient(**fields))


async def make_audit(session: AsyncSession, user: User) -> Audit:
    """An Audit whose own writes join the test's transaction through savepoints."""
    sessionmaker = async_sessionmaker(
        bind=await session.connection(),
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    return Audit(user, session, BackgroundTasks(), sessionmaker)


async def add_to_care_team(
    session: AsyncSession, patient: Patient, user: User, role: str = "nurse"
) -> None:
    session.add(CareTeamMember(patient_id=patient.id, user_id=user.id, role=role))
    await session.flush()


async def add_visit(
    session: AsyncSession, patient: Patient, provider: User, when: datetime, status: str
) -> None:
    session.add(
        Visit(patient_id=patient.id, provider_id=provider.id, scheduled_at=when, status=status)
    )
    await session.flush()
