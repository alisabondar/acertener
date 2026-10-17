from datetime import UTC, date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import AuditAction, AuditEntry
from app.crypto import FieldCipher
from app.db.models import Note, PatientSummary, Visit
from app.patients.repository import NewPatient, PatientRepository
from scripts.prove_encryption import database_as_text
from tests.factories import make_audit, make_user

pytestmark = [pytest.mark.db, pytest.mark.anyio]

CANARY = NewPatient(
    first_name="Quillonfirst",
    last_name="Zyxcanary",
    mrn="MRN-CANARY-9071",
    dob=date(1931, 7, 19),
    gender="canarygender",
    phone="555-867-5309",
    email="zyx.canary@example.test",
    address_line1="742 Canarywood Lane",
    address_line2="Suite Canary",
    city="Canaryville",
    state="Canarystate",
    postal_code="90717",
)
CANARY_VALUES = [
    v.isoformat() if isinstance(v, date) else v for v in vars(CANARY).values() if v
] + ["07/19/1931"]
VISIT_REASON = "Zyxcanary's daughter Quillonkin called about the rash"
NOTE_CONTENT = "Spoke with Quillonkin Zyxcanary (son), call back on 555-867-5309"
SUMMARY_CONTENT = "Zyxcanary is a 94-year-old patient at Canarywood Lane"
CANARY_VALUES += [VISIT_REASON, NOTE_CONTENT, SUMMARY_CONTENT]


async def test_no_plaintext_phi_at_rest(
    db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    patient = await PatientRepository(db_session, field_cipher).create(CANARY)
    provider = make_user()
    db_session.add(provider)
    await db_session.flush()
    audit = await make_audit(db_session, provider)
    await audit.record_change(
        AuditEntry(
            AuditAction.UPDATE,
            "patient",
            patient.id,
            patient.id,
            {"last_name": ("Zyxcanary", "Zyxcanary-Smith"), "phone": ("555-867-5309", None)},
        )
    )
    db_session.add(
        Visit(
            patient_id=patient.id,
            provider_id=provider.id,
            scheduled_at=datetime.now(UTC),
            reason=VISIT_REASON,
        )
    )
    db_session.add_all(
        [
            Note(
                patient_id=patient.id,
                author_id=provider.id,
                encounter_at=datetime.now(UTC),
                content=NOTE_CONTENT,
            ),
            PatientSummary(patient_id=patient.id, content=SUMMARY_CONTENT, status="fresh"),
        ]
    )
    await db_session.flush()

    dump = (await database_as_text(db_session)).casefold()

    leaked = [v for v in CANARY_VALUES if v.casefold() in dump or v.encode().hex() in dump]
    assert leaked == []
