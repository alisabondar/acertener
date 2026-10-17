import uuid
from datetime import UTC, date, datetime

import httpx2
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import AuditAction, AuditEntry
from app.crypto import FieldCipher
from app.db.models import AuditLog
from app.patients.repository import PatientRepository
from tests.factories import add_to_care_team, add_user, create_patient, make_audit, persona_headers

pytestmark = [pytest.mark.db, pytest.mark.anyio]

CANARY = "Zyxcanary"
CLINICAL_FIELDS = {"notes", "vitals", "allergies", "conditions", "summary"}


@pytest.mark.parametrize("role", ["provider", "nurse", "front_desk", "admin"])
async def test_every_role_sees_demographics_and_nothing_clinical(
    api: httpx2.AsyncClient, db_session: AsyncSession, field_cipher: FieldCipher, role: str
) -> None:
    viewer = await add_user(db_session, role, credential=None)
    patient = await create_patient(
        db_session, field_cipher, dob=date(datetime.now(UTC).year - 30, 1, 1), city="Springfield"
    )
    await add_to_care_team(db_session, patient, viewer)

    response = await api.get(f"/api/v1/patients/{patient.id}", headers=persona_headers(viewer))

    assert response.status_code == 200
    body = response.json()
    assert (body["id"], body["last_name"], body["city"], body["age"]) == (
        str(patient.id),
        "Smith",
        "Springfield",
        30,
    )
    assert (body["on_my_care_team"], body["archived"], body["version"]) == (True, False, 1)
    assert not CLINICAL_FIELDS & body.keys()


async def test_unknown_patient_is_a_404(api: httpx2.AsyncClient, db_session: AsyncSession) -> None:
    viewer = await add_user(db_session)

    response = await api.get(f"/api/v1/patients/{uuid.uuid4()}", headers=persona_headers(viewer))

    assert response.status_code == 404
    assert response.json()["code"] == "PATIENT_NOT_FOUND"


async def test_archived_patients_are_still_viewable(
    api: httpx2.AsyncClient, db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    viewer = await add_user(db_session)
    patient = await create_patient(db_session, field_cipher)
    await PatientRepository(db_session, field_cipher).update(
        patient.id, archived_at=datetime.now(UTC), archive_reason="duplicate"
    )

    body = (await api.get(f"/api/v1/patients/{patient.id}", headers=persona_headers(viewer))).json()

    assert (body["archived"], body["archive_reason"]) == (True, "duplicate")


async def test_viewing_a_patient_is_audited_for_that_patient(
    api: httpx2.AsyncClient, db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    viewer = await add_user(db_session)
    patient = await create_patient(db_session, field_cipher)

    await api.get(f"/api/v1/patients/{patient.id}", headers=persona_headers(viewer))

    [entry] = await db_session.scalars(select(AuditLog))
    assert (entry.action, entry.entity, entry.patient_id, entry.actor_id) == (
        "view",
        "patient",
        patient.id,
        viewer.id,
    )


async def test_access_log_lists_this_patients_history_without_values(
    api: httpx2.AsyncClient, db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    nurse = await add_user(db_session, "nurse", name="Sam Okafor", credential="RN")
    patient = await create_patient(db_session, field_cipher)
    other = await create_patient(db_session, field_cipher)
    audit = await make_audit(db_session, nurse)
    await audit.record_change(
        AuditEntry(AuditAction.UPDATE, "patient", patient.id, patient.id, {"phone": (CANARY, "2")})
    )
    await audit.record_change(AuditEntry(AuditAction.VIEW, "patient", other.id, other.id))

    response = await api.get(
        f"/api/v1/patients/{patient.id}/access-log", headers=persona_headers(nurse)
    )

    assert response.status_code == 200
    [item] = response.json()["items"]
    assert (item["actor_name"], item["actor_role"], item["action"]) == (
        "Sam Okafor",
        "nurse",
        "update",
    )
    assert item["changed_fields"] == ["phone"]
    assert CANARY not in response.text


async def test_viewing_the_access_log_is_itself_audited(
    api: httpx2.AsyncClient, db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    admin = await add_user(db_session, "admin", credential=None)
    patient = await create_patient(db_session, field_cipher)

    await api.get(f"/api/v1/patients/{patient.id}/access-log", headers=persona_headers(admin))

    entities = [e.entity for e in await db_session.scalars(select(AuditLog))]
    assert entities == ["patient_access_log"]


async def test_front_desk_cannot_see_access_history(
    api: httpx2.AsyncClient, db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    front_desk = await add_user(db_session, "front_desk", credential=None)
    patient = await create_patient(db_session, field_cipher)

    response = await api.get(
        f"/api/v1/patients/{patient.id}/access-log", headers=persona_headers(front_desk)
    )

    assert response.status_code == 403


async def test_only_uuids_route_to_a_patient(
    api: httpx2.AsyncClient, db_session: AsyncSession
) -> None:
    viewer = await add_user(db_session)

    response = await api.get("/api/v1/patients/not-a-uuid", headers=persona_headers(viewer))

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"
