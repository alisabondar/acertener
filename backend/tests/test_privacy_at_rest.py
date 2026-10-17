from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import FieldCipher
from app.patients.repository import NewPatient, PatientRepository
from scripts.prove_encryption import database_as_text

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


async def test_no_plaintext_phi_at_rest(
    db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    await PatientRepository(db_session, field_cipher).create(CANARY)

    dump = (await database_as_text(db_session)).casefold()

    leaked = [v for v in CANARY_VALUES if v.casefold() in dump or v.encode().hex() in dump]
    assert leaked == []
