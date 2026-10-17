from datetime import date

import pytest
from sqlalchemy import column, select, table, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Patient

pytestmark = [pytest.mark.db, pytest.mark.anyio]

CANARY = "CanarySmith"
ENCRYPTED_COLUMNS = [
    "first_name", "last_name", "mrn", "dob", "gender", "phone", "email",
    "address_line1", "address_line2", "city", "state", "postal_code",
]  # fmt: skip


def make_patient(**overrides: object) -> Patient:
    fields: dict[str, object] = {
        "first_name": "José",
        "last_name": CANARY,
        "mrn": "MRN-000123",
        "dob": date(1984, 2, 29),
        "gender": "female",
        "phone": "555-0100",
        "email": "canary@example.test",
        "address_line1": "1 Canary Way",
        "address_line2": "Apt 2",
        "city": "Springfield",
        "state": "IL",
        "postal_code": "62701",
        "birth_year": 1984,
        "last_name_fp": b"\x01" * 32,
        "dob_fp": b"\x02" * 32,
        "mrn_fp": b"\x03" * 32,
    }
    fields.update(overrides)
    return Patient(**fields)


async def test_patient_round_trips_through_the_database(db_session: AsyncSession) -> None:
    patient = make_patient()
    db_session.add(patient)
    await db_session.commit()
    db_session.expunge_all()

    loaded = await db_session.scalar(select(Patient).where(Patient.id == patient.id))

    assert loaded is not None
    assert (loaded.first_name, loaded.last_name, loaded.dob) == ("José", CANARY, date(1984, 2, 29))
    assert loaded.postal_code == "62701"
    assert loaded.status == "active"
    assert loaded.version == 1
    assert loaded.created_at.tzinfo is not None


async def test_identifiers_are_stored_as_ciphertext(db_session: AsyncSession) -> None:
    patient = make_patient()
    db_session.add(patient)
    await db_session.commit()

    # Untyped columns read the stored text as-is, bypassing decryption.
    raw_patients = table("patients", column("id"), *(column(c) for c in ENCRYPTED_COLUMNS))
    row = (
        await db_session.execute(
            select(*(raw_patients.c[c] for c in ENCRYPTED_COLUMNS)).where(
                raw_patients.c.id == patient.id
            )
        )
    ).one()

    for name, raw in zip(ENCRYPTED_COLUMNS, row, strict=True):
        assert raw.startswith("v1:"), name
    assert all(CANARY not in raw for raw in row)


async def test_null_stays_null(db_session: AsyncSession) -> None:
    patient = make_patient(address_line2=None, gender=None)
    db_session.add(patient)
    await db_session.commit()

    raw = (
        await db_session.execute(
            text("SELECT address_line2, gender FROM patients WHERE id = :id"), {"id": patient.id}
        )
    ).one()

    assert tuple(raw) == (None, None)


async def test_invalid_status_is_rejected(db_session: AsyncSession) -> None:
    db_session.add(make_patient(status="asleep"))

    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_duplicate_mrn_is_rejected(db_session: AsyncSession) -> None:
    db_session.add(make_patient())
    await db_session.commit()
    db_session.add(make_patient(last_name="Other"))

    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_version_has_room_for_years_of_autosaves(db_session: AsyncSession) -> None:
    patient = make_patient()
    db_session.add(patient)
    await db_session.commit()

    await db_session.execute(
        text("UPDATE patients SET version = 100000 WHERE id = :id"), {"id": patient.id}
    )
