import uuid
from datetime import date
from typing import Any

import httpx2
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.log import Audit
from app.crypto import FieldCipher
from app.db.models import AuditLog, Patient, User
from app.patients.repository import PatientRepository
from tests.factories import add_user, create_patient, persona_headers

pytestmark = [pytest.mark.db, pytest.mark.anyio]

CANARY = "Zyxcanary"


def _new(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "first_name": "Ada",
        "last_name": CANARY,
        "mrn": "MRN-900001",
        "dob": "1984-02-29",
        "gender": "female",
        "phone": "555-555-0100",
        "blood_type": "O-",
    }
    body.update(overrides)
    return body


async def _create(api: httpx2.AsyncClient, user: User, **overrides: Any) -> httpx2.Response:
    return await api.post("/api/v1/patients", json=_new(**overrides), headers=persona_headers(user))


async def _patch(
    api: httpx2.AsyncClient, user: User, patient_id: Any, base_version: int, **changes: Any
) -> httpx2.Response:
    return await api.patch(
        f"/api/v1/patients/{patient_id}",
        json={"base_version": base_version, "changes": changes},
        headers=persona_headers(user),
    )


async def _audit(session: AsyncSession, action: str) -> list[AuditLog]:
    return list(await session.scalars(select(AuditLog).where(AuditLog.action == action)))


async def _patient_count(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count()).select_from(Patient)) or 0)


@pytest.mark.parametrize(
    ("role", "joins_care_team"), [("provider", True), ("nurse", True), ("front_desk", False)]
)
async def test_create_returns_201_and_adds_clinical_creators_to_the_care_team(
    api: httpx2.AsyncClient, db_session: AsyncSession, role: str, joins_care_team: bool
) -> None:
    creator = await add_user(db_session, role)

    response = await _create(api, creator)

    assert response.status_code == 201
    body = response.json()
    assert (body["last_name"], body["dob"], body["version"]) == (CANARY, "1984-02-29", 1)
    # Clinical data: front desk can enter it but doesn't get it back.
    assert body["blood_type"] == ("O-" if role in ("provider", "nurse") else None)
    assert body["on_my_care_team"] is joins_care_team
    [entry] = await _audit(db_session, "create")
    assert (str(entry.patient_id), entry.actor_id) == (body["id"], creator.id)


async def test_admins_cannot_create_patients(
    api: httpx2.AsyncClient, db_session: AsyncSession
) -> None:
    response = await _create(api, await add_user(db_session, "admin"))

    assert response.status_code == 403


@pytest.mark.parametrize(
    "overrides",
    [{"dob": "2999-01-01"}, {"last_name": ""}, {"gender": "unknown-value"}, {"mrn": None}],
    ids=["dob-in-future", "blank-last-name", "bad-gender", "missing-mrn"],
)
async def test_invalid_input_is_a_422(
    api: httpx2.AsyncClient, db_session: AsyncSession, overrides: dict[str, Any]
) -> None:
    response = await _create(api, await add_user(db_session), **overrides)

    assert response.status_code == 422


async def test_likely_duplicate_warns_and_can_be_overridden(
    api: httpx2.AsyncClient, db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    creator = await add_user(db_session)
    existing = await create_patient(
        db_session, field_cipher, last_name=CANARY, dob=date(1984, 2, 29)
    )

    warned = await _create(api, creator, first_name="Twin")
    confirmed = await _create(api, creator, first_name="Twin", confirm_not_duplicate=True)

    assert warned.status_code == 409
    assert warned.json()["code"] == "POSSIBLE_DUPLICATE"
    assert warned.json()["matches"] == [str(existing.id)]
    assert CANARY not in warned.text
    assert confirmed.status_code == 201
    detail = await api.get(
        f"/api/v1/patients/{confirmed.json()['id']}/access-log",
        headers=persona_headers(creator),
    )
    assert "duplicate_override" in detail.json()["items"][-1]["changed_fields"]


async def test_duplicate_mrn_is_a_hard_409_on_create_and_edit(
    api: httpx2.AsyncClient, db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    creator = await add_user(db_session)
    holder = await create_patient(db_session, field_cipher, mrn="MRN-555")
    other = await create_patient(db_session, field_cipher, mrn="MRN-556", last_name="Other")

    created = await _create(api, creator, mrn=" mrn-555 ", confirm_not_duplicate=True)
    edited = await _patch(api, creator, other.id, 1, mrn="MRN-555")

    for response in (created, edited):
        assert response.status_code == 409
        assert response.json()["code"] == "DUPLICATE_MRN"
        assert "555" not in response.json()["detail"]
        # Points at the patient who has the MRN, so the form can link to their chart.
        assert response.json()["matches"] == [str(holder.id)]


async def test_edit_saves_and_audits_only_changed_fields(
    api: httpx2.AsyncClient, db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    editor = await add_user(db_session, "front_desk")
    patient = await create_patient(
        db_session, field_cipher, city="Springfield", phone="555-555-0100"
    )

    response = await _patch(api, editor, patient.id, 1, city="Shelbyville", phone="555-555-0100")

    assert response.status_code == 200
    assert (response.json()["city"], response.json()["version"]) == ("Shelbyville", 2)
    [entry] = await _audit(db_session, "update")
    assert entry.actor_id == editor.id
    log = await api.get(
        f"/api/v1/patients/{patient.id}/access-log",
        headers=persona_headers(await add_user(db_session, "admin")),
    )
    assert log.json()["items"][0]["changed_fields"] == ["city"]


async def test_stale_base_version_is_a_409_with_the_current_record(
    api: httpx2.AsyncClient, db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    editor = await add_user(db_session)
    patient = await create_patient(db_session, field_cipher, city="Springfield")
    await _patch(api, editor, patient.id, 1, city="Shelbyville")

    stale = await _patch(api, editor, patient.id, 1, city="Capital City")

    assert stale.status_code == 409
    body = stale.json()
    assert body["code"] == "VERSION_CONFLICT"
    assert (body["current"]["city"], body["current"]["version"]) == ("Shelbyville", 2)
    assert len(await _audit(db_session, "update")) == 1


async def test_renaming_keeps_search_working(
    api: httpx2.AsyncClient, db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    editor = await add_user(db_session)
    patient = await create_patient(db_session, field_cipher, last_name="Smith")

    await _patch(api, editor, patient.id, 1, last_name="Jones")

    repo = PatientRepository(db_session, field_cipher)
    assert await repo.search(last_name="smi") == []
    assert [p.id for p in await repo.search(last_name="jon")] == [patient.id]


async def test_editing_an_unknown_patient_is_a_404(
    api: httpx2.AsyncClient, db_session: AsyncSession
) -> None:
    response = await _patch(api, await add_user(db_session), uuid.uuid4(), 1, city="X")

    assert response.status_code == 404


async def test_admins_cannot_edit_demographics(
    api: httpx2.AsyncClient, db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    patient = await create_patient(db_session, field_cipher)

    response = await _patch(api, await add_user(db_session, "admin"), patient.id, 1, city="X")

    assert response.status_code == 403


async def test_a_failed_audit_write_rolls_back_the_change(
    api: httpx2.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken(*_: object, **__: object) -> None:
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(Audit, "record_change", broken)

    response = await _create(api, await add_user(db_session))

    assert response.status_code == 500
    assert await _patient_count(db_session) == 0


async def test_put_replaces_every_field_and_clears_the_ones_left_out(
    api: httpx2.AsyncClient, db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    editor = await add_user(db_session, "front_desk")
    patient = await create_patient(
        db_session, field_cipher, city="Springfield", phone="555-555-0100"
    )
    url = f"/api/v1/patients/{patient.id}"
    full = {"first_name": "Ada", "last_name": "Jones", "mrn": patient.mrn, "dob": "1990-01-31"}

    replaced = await api.put(url, json={"base_version": 1, **full}, headers=persona_headers(editor))
    stale = await api.put(url, json={"base_version": 1, **full}, headers=persona_headers(editor))

    assert replaced.status_code == 200
    body = replaced.json()
    assert (body["last_name"], body["city"], body["phone"], body["version"]) == (
        "Jones",
        None,
        None,
        2,
    )
    assert stale.status_code == 409


async def test_put_leaves_clinical_fields_alone_for_roles_that_cant_see_them(
    api: httpx2.AsyncClient, db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    desk = await add_user(db_session, "front_desk")
    nurse = await add_user(db_session, "nurse")
    patient = await create_patient(db_session, field_cipher, blood_type="AB-")
    url = f"/api/v1/patients/{patient.id}"
    full = {"first_name": "Ada", "last_name": "Jones", "mrn": patient.mrn, "dob": "1990-01-31"}

    await api.put(url, json={"base_version": 1, **full}, headers=persona_headers(desk))
    seen_by_nurse = await api.get(url, headers=persona_headers(nurse))

    assert seen_by_nurse.json()["blood_type"] == "AB-"
