from datetime import UTC, date, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import FieldCipher
from app.db.models import CareTeamMember, Visit
from tests.factories import create_patient, make_user

pytestmark = [pytest.mark.db, pytest.mark.anyio]


@pytest.mark.parametrize(("field", "value"), [("role", "wizard"), ("credential", "XYZ")])
async def test_user_role_and_credential_are_constrained(
    db_session: AsyncSession, field: str, value: str
) -> None:
    db_session.add(make_user(**{field: value}))

    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_visit_status_is_constrained(
    db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    provider = make_user()
    db_session.add(provider)
    patient = await create_patient(db_session, field_cipher)
    db_session.add(
        Visit(
            patient_id=patient.id,
            provider_id=provider.id,
            scheduled_at=datetime.now(UTC),
            status="maybe",
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_a_user_has_one_active_membership_per_care_team(
    db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    nurse = make_user(role="nurse", credential="RN")
    db_session.add(nurse)
    patient = await create_patient(db_session, field_cipher)
    await db_session.flush()

    ended = CareTeamMember(
        patient_id=patient.id,
        user_id=nurse.id,
        role="nurse",
        start_date=date(2020, 1, 1),
        end_date=date(2021, 1, 1),
    )
    db_session.add_all(
        [ended, CareTeamMember(patient_id=patient.id, user_id=nurse.id, role="nurse")]
    )
    await db_session.flush()

    db_session.add(CareTeamMember(patient_id=patient.id, user_id=nurse.id, role="nurse"))
    with pytest.raises(IntegrityError):
        await db_session.flush()
