import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import httpx2
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import FieldCipher
from app.db.models import AuditLog, Patient, PatientSummary, User
from app.patients.repository import PatientRepository
from tests.factories import add_user, create_patient, persona_headers

pytestmark = [pytest.mark.db, pytest.mark.anyio]

NOTE_TEXT = "Zyxcanary reports a cough for three days."
VITALS = {"bp_systolic": 128, "bp_diastolic": 82, "heart_rate": 72, "spo2": 98}
ALLERGY = {"substance": "Penicillin", "reaction": "Hives", "severity": "severe"}
CONDITION = {"icd10_code": "E11.9", "name": "Type 2 diabetes"}

Api = httpx2.AsyncClient


@pytest.fixture
async def patient(db_session: AsyncSession, field_cipher: FieldCipher) -> Patient:
    return await create_patient(db_session, field_cipher)


async def _user(session: AsyncSession, role: str) -> User:
    return await add_user(session, role)


def _ok(response: httpx2.Response, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json() if response.content else None


async def _draft(api: Api, author: User, patient: Patient, text: str = NOTE_TEXT) -> Any:
    response = await api.post(
        f"/api/v1/patients/{patient.id}/notes",
        json={"content": text},
        headers=persona_headers(author),
    )
    return _ok(response, 201)


# --- Permissions --------------------------------------------------------------------------

Action = Callable[[Api, User, Patient], Awaitable[httpx2.Response]]

ACTIONS: dict[str, Action] = {
    "read notes": lambda api, u, p: api.get(
        f"/api/v1/patients/{p.id}/notes", headers=persona_headers(u)
    ),
    "write a note": lambda api, u, p: api.post(
        f"/api/v1/patients/{p.id}/notes", json={"content": "x"}, headers=persona_headers(u)
    ),
    "read vitals": lambda api, u, p: api.get(
        f"/api/v1/patients/{p.id}/vitals", headers=persona_headers(u)
    ),
    "record vitals": lambda api, u, p: api.post(
        f"/api/v1/patients/{p.id}/vitals", json=VITALS, headers=persona_headers(u)
    ),
    "add an allergy": lambda api, u, p: api.post(
        f"/api/v1/patients/{p.id}/allergies", json=ALLERGY, headers=persona_headers(u)
    ),
    "add a condition": lambda api, u, p: api.post(
        f"/api/v1/patients/{p.id}/conditions", json=CONDITION, headers=persona_headers(u)
    ),
}

# role -> action -> expected status, straight from the permission matrix.
EXPECTED = {
    "provider": {
        "read notes": 200,
        "write a note": 201,
        "read vitals": 200,
        "record vitals": 201,
        "add an allergy": 201,
        "add a condition": 201,
    },
    "nurse": {
        "read notes": 200,
        "write a note": 201,
        "read vitals": 200,
        "record vitals": 201,
        "add an allergy": 201,
        "add a condition": 403,
    },
    "front_desk": dict.fromkeys(ACTIONS, 403),
    "admin": dict.fromkeys(ACTIONS, 403),
}


@pytest.mark.parametrize(
    ("role", "action"), [(role, action) for role in EXPECTED for action in ACTIONS]
)
async def test_clinical_permissions_follow_the_matrix(
    api: Api, db_session: AsyncSession, patient: Patient, role: str, action: str
) -> None:
    user = await _user(db_session, role)

    response = await ACTIONS[action](api, user, patient)

    assert response.status_code == EXPECTED[role][action], response.text


async def test_a_nurse_cant_add_a_diagnosis(
    api: Api, db_session: AsyncSession, patient: Patient
) -> None:
    nurse = await _user(db_session, "nurse")

    response = await api.post(
        f"/api/v1/patients/{patient.id}/conditions", json=CONDITION, headers=persona_headers(nurse)
    )

    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"


async def test_clinical_routes_404_for_an_unknown_patient(
    api: Api, db_session: AsyncSession
) -> None:
    provider = await _user(db_session, "provider")

    response = await api.get(
        f"/api/v1/patients/{uuid.uuid4()}/notes", headers=persona_headers(provider)
    )

    assert response.status_code == 404
    assert response.json()["code"] == "PATIENT_NOT_FOUND"


async def test_an_archived_chart_takes_no_new_clinical_entries(
    api: Api, db_session: AsyncSession, field_cipher: FieldCipher, patient: Patient
) -> None:
    provider = await _user(db_session, "provider")
    await PatientRepository(db_session, field_cipher).update(
        patient.id, archived_at=datetime.now(UTC)
    )

    response = await api.post(
        f"/api/v1/patients/{patient.id}/vitals", json=VITALS, headers=persona_headers(provider)
    )

    assert response.status_code == 409
    assert response.json()["code"] == "INVALID_STATE"


# --- Notes ---------------------------------------------------------------------------------


async def test_a_note_goes_from_draft_to_final_and_then_stays_put(
    api: Api, db_session: AsyncSession, patient: Patient
) -> None:
    author = await _user(db_session, "provider")
    headers = persona_headers(author)
    note = await _draft(api, author, patient)
    assert note["status"] == "draft"

    edited = _ok(
        await api.patch(f"/api/v1/notes/{note['id']}", json={"content": "Edited"}, headers=headers)
    )
    final = _ok(await api.post(f"/api/v1/notes/{note['id']}/finalize", headers=headers))
    again = await api.patch(
        f"/api/v1/notes/{note['id']}", json={"content": "Too late"}, headers=headers
    )
    removed = await api.delete(f"/api/v1/notes/{note['id']}", headers=headers)

    assert edited["content"] == "Edited"
    assert (final["status"], final["finalized_at"] is not None) == ("final", True)
    assert (again.status_code, again.json()["code"]) == (409, "NOTE_FINALIZED")
    assert (removed.status_code, removed.json()["code"]) == (409, "NOTE_FINALIZED")


async def test_only_the_author_edits_finalizes_or_deletes_a_draft(
    api: Api, db_session: AsyncSession, patient: Patient
) -> None:
    author = await _user(db_session, "provider")
    colleague = await _user(db_session, "nurse")
    note = await _draft(api, author, patient)
    theirs = persona_headers(colleague)

    attempts = [
        await api.patch(f"/api/v1/notes/{note['id']}", json={"content": "x"}, headers=theirs),
        await api.post(f"/api/v1/notes/{note['id']}/finalize", headers=theirs),
        await api.delete(f"/api/v1/notes/{note['id']}", headers=theirs),
    ]

    assert [(r.status_code, r.json()["code"]) for r in attempts] == [(403, "NOT_NOTE_AUTHOR")] * 3


async def test_the_author_deletes_a_draft_and_it_disappears(
    api: Api, db_session: AsyncSession, patient: Patient
) -> None:
    author = await _user(db_session, "provider")
    headers = persona_headers(author)
    note = await _draft(api, author, patient)

    response = await api.delete(f"/api/v1/notes/{note['id']}", headers=headers)
    listed = _ok(await api.get(f"/api/v1/patients/{patient.id}/notes", headers=headers))

    assert response.status_code == 204
    assert listed["items"] == []


async def test_notes_list_shows_final_notes_and_only_my_own_drafts(
    api: Api, db_session: AsyncSession, patient: Patient
) -> None:
    me = await _user(db_session, "provider")
    colleague = await _user(db_session, "nurse")
    final = await _draft(api, colleague, patient, "Final by colleague")
    await api.post(f"/api/v1/notes/{final['id']}/finalize", headers=persona_headers(colleague))
    await _draft(api, colleague, patient, "Colleague's draft")
    await _draft(api, me, patient, "My draft")

    listed = _ok(await api.get(f"/api/v1/patients/{patient.id}/notes", headers=persona_headers(me)))

    assert sorted(n["content"] for n in listed["items"]) == ["Final by colleague", "My draft"]
    assert {n["author_name"] for n in listed["items"]} == {me.name, colleague.name}


async def test_note_text_never_appears_in_errors_or_audit_rows(
    api: Api, db_session: AsyncSession, patient: Patient
) -> None:
    author = await _user(db_session, "provider")
    note = await _draft(api, author, patient)
    await api.post(f"/api/v1/notes/{note['id']}/finalize", headers=persona_headers(author))

    refused = await api.patch(
        f"/api/v1/notes/{note['id']}", json={"content": NOTE_TEXT}, headers=persona_headers(author)
    )
    raw = await db_session.execute(select(AuditLog.changes).where(AuditLog.entity == "note"))
    stored = " ".join(str(value) for (value,) in raw)

    assert "Zyxcanary" not in refused.text
    # Audit `changes` are encrypted at rest, so the raw column never holds the text either.
    assert "Zyxcanary" not in stored


# --- Vitals --------------------------------------------------------------------------------


async def test_vitals_are_recorded_and_listed_newest_first(
    api: Api, db_session: AsyncSession, patient: Patient
) -> None:
    nurse = await _user(db_session, "nurse")
    headers = persona_headers(nurse)
    url = f"/api/v1/patients/{patient.id}/vitals"
    _ok(
        await api.post(url, json={**VITALS, "taken_at": "2026-01-01T09:00:00Z"}, headers=headers),
        201,
    )
    _ok(
        await api.post(
            url, json={"heart_rate": 90, "taken_at": "2026-02-01T09:00:00Z"}, headers=headers
        ),
        201,
    )

    items = _ok(await api.get(url, headers=headers))["items"]

    assert [i["heart_rate"] for i in items] == [90, 72]
    assert items[1]["bp_systolic"] == 128
    assert items[0]["recorded_by_name"] == nurse.name


@pytest.mark.parametrize(
    ("values", "field"),
    [
        ({"bp_systolic": 300, "bp_diastolic": 80}, "bp_systolic"),
        ({"bp_systolic": 120, "bp_diastolic": 130}, "bp_diastolic"),
        ({"heart_rate": 5}, "heart_rate"),
        ({"spo2": 101}, "spo2"),
        ({"temperature_c": 50}, "temperature_c"),
    ],
)
async def test_vitals_outside_physiologic_ranges_get_field_errors(
    api: Api, db_session: AsyncSession, patient: Patient, values: dict[str, Any], field: str
) -> None:
    nurse = await _user(db_session, "nurse")

    response = await api.post(
        f"/api/v1/patients/{patient.id}/vitals", json=values, headers=persona_headers(nurse)
    )

    assert response.status_code == 422
    assert field in response.json()["errors"]


async def test_a_vitals_entry_needs_at_least_one_reading(
    api: Api, db_session: AsyncSession, patient: Patient
) -> None:
    nurse = await _user(db_session, "nurse")

    response = await api.post(
        f"/api/v1/patients/{patient.id}/vitals", json={}, headers=persona_headers(nurse)
    )

    assert response.status_code == 422


# --- Allergies & conditions -----------------------------------------------------------------


async def test_allergies_are_edited_and_resolved_but_never_deleted(
    api: Api, db_session: AsyncSession, patient: Patient
) -> None:
    nurse = await _user(db_session, "nurse")
    headers = persona_headers(nurse)
    allergy = _ok(
        await api.post(f"/api/v1/patients/{patient.id}/allergies", json=ALLERGY, headers=headers),
        201,
    )

    edited = _ok(
        await api.patch(
            f"/api/v1/allergies/{allergy['id']}", json={"reaction": "Anaphylaxis"}, headers=headers
        )
    )
    resolved = _ok(
        await api.post(
            f"/api/v1/allergies/{allergy['id']}/status",
            json={"status": "resolved"},
            headers=headers,
        )
    )
    deleted = await api.delete(f"/api/v1/allergies/{allergy['id']}", headers=headers)
    listed = _ok(await api.get(f"/api/v1/patients/{patient.id}/allergies", headers=headers))

    assert (edited["reaction"], edited["severity"]) == ("Anaphylaxis", "severe")
    assert resolved["status"] == "resolved"
    assert deleted.status_code == 405
    assert [a["status"] for a in listed["items"]] == ["resolved"]


async def test_a_condition_can_be_marked_entered_in_error_by_a_provider(
    api: Api, db_session: AsyncSession, patient: Patient
) -> None:
    provider = await _user(db_session, "provider")
    headers = persona_headers(provider)
    condition = _ok(
        await api.post(
            f"/api/v1/patients/{patient.id}/conditions", json=CONDITION, headers=headers
        ),
        201,
    )

    changed = _ok(
        await api.post(
            f"/api/v1/conditions/{condition['id']}/status",
            json={"status": "entered_in_error"},
            headers=headers,
        )
    )

    assert (changed["status"], changed["icd10_code"]) == ("entered_in_error", "E11.9")


@pytest.mark.parametrize(
    ("kind", "body", "field"),
    [
        ("allergies", ALLERGY, "substance"),
        ("conditions", CONDITION, "icd10_code"),
        ("conditions", CONDITION, "name"),
    ],
)
async def test_required_fields_cant_be_cleared(
    api: Api,
    db_session: AsyncSession,
    patient: Patient,
    kind: str,
    body: dict[str, Any],
    field: str,
) -> None:
    provider = await _user(db_session, "provider")
    headers = persona_headers(provider)
    created = _ok(
        await api.post(f"/api/v1/patients/{patient.id}/{kind}", json=body, headers=headers), 201
    )

    response = await api.patch(
        f"/api/v1/{kind}/{created['id']}", json={field: None}, headers=headers
    )

    assert response.status_code == 422
    assert field in response.json()["errors"]


async def test_allergy_severity_must_be_known(
    api: Api, db_session: AsyncSession, patient: Patient
) -> None:
    nurse = await _user(db_session, "nurse")

    response = await api.post(
        f"/api/v1/patients/{patient.id}/allergies",
        json={**ALLERGY, "severity": "lethal"},
        headers=persona_headers(nurse),
    )

    assert response.status_code == 422
    assert "severity" in response.json()["errors"]


# --- Summary & audit --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "action", ["write a note", "record vitals", "add an allergy", "add a condition"]
)
async def test_every_clinical_write_marks_the_summary_stale(
    api: Api, db_session: AsyncSession, patient: Patient, action: str
) -> None:
    provider = await _user(db_session, "provider")
    db_session.add(PatientSummary(patient_id=patient.id, status="fresh"))
    await db_session.flush()

    await ACTIONS[action](api, provider, patient)

    summary = await db_session.get(PatientSummary, patient.id, populate_existing=True)
    assert summary is not None
    assert summary.status == "stale"
    assert summary.source_changed_at is not None


async def test_clinical_writes_and_reads_are_audited(
    api: Api, db_session: AsyncSession, patient: Patient
) -> None:
    provider = await _user(db_session, "provider")
    note = await _draft(api, provider, patient)
    await api.get(f"/api/v1/patients/{patient.id}/notes", headers=persona_headers(provider))

    entries = list(await db_session.scalars(select(AuditLog).order_by(AuditLog.id)))

    assert [(e.action, e.entity, e.patient_id) for e in entries] == [
        ("create", "note", patient.id),
        ("view", "notes", patient.id),
    ]
    assert entries[0].entity_id == uuid.UUID(note["id"])
