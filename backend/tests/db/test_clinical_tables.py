from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import FieldCipher
from app.db.models import Allergy, Base, Condition, Note, PatientSummary
from tests.factories import create_patient, make_user

pytestmark = [pytest.mark.db, pytest.mark.anyio]

Row = Callable[[Any, Any], Base]


def allergy(**kw: Any) -> Row:
    return lambda p, u: Allergy(patient_id=p, recorded_by=u, substance="Penicillin", **kw)


def condition(**kw: Any) -> Row:
    return lambda p, u: Condition(
        patient_id=p, recorded_by=u, icd10_code="E11.9", name="Type 2 diabetes", **kw
    )


def note(**kw: Any) -> Row:
    return lambda p, u: Note(
        patient_id=p, author_id=u, encounter_at=datetime.now(UTC), content="Seen today", **kw
    )


def summary(**kw: Any) -> Row:
    return lambda p, u: PatientSummary(patient_id=p, **kw)


async def _insert(session: AsyncSession, cipher: FieldCipher, build: Row) -> None:
    user = make_user()
    session.add(user)
    patient = await create_patient(session, cipher)
    session.add(build(patient.id, user.id))
    await session.flush()


@pytest.mark.parametrize(
    "build",
    [
        allergy(status="gone"),
        allergy(severity="extreme"),
        condition(status="cured"),
        note(status="published"),
        note(status="final"),  # final without finalized_at
        summary(status="sleepy"),
    ],
    ids=[
        "allergy-status",
        "allergy-severity",
        "condition-status",
        "note-status",
        "final-note-needs-finalized-at",
        "summary-status",
    ],
)
async def test_clinical_values_are_constrained(
    db_session: AsyncSession, field_cipher: FieldCipher, build: Row
) -> None:
    with pytest.raises(IntegrityError):
        await _insert(db_session, field_cipher, build)


@pytest.mark.parametrize(
    "build",
    [
        allergy(reaction="Hives", severity="moderate"),
        condition(),
        note(status="final", finalized_at=datetime.now(UTC)),
    ],
    ids=["allergy", "condition", "final-note"],
)
async def test_valid_clinical_rows_are_accepted(
    db_session: AsyncSession, field_cipher: FieldCipher, build: Row
) -> None:
    await _insert(db_session, field_cipher, build)
