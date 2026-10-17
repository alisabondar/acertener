from typing import Any

import httpx2
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.log import Audit
from app.crypto import FieldCipher
from app.db.models import AuditLog, Patient, User
from tests.factories import add_user, create_patient, persona_headers

pytestmark = [pytest.mark.db, pytest.mark.anyio]


async def _act(
    api: httpx2.AsyncClient, user: User, patient: Patient, action: str, **body: Any
) -> httpx2.Response:
    body.setdefault("base_version", 1)
    return await api.post(
        f"/api/v1/patients/{patient.id}/{action}", json=body, headers=persona_headers(user)
    )


async def _list_ids(api: httpx2.AsyncClient, user: User, **params: Any) -> set[str]:
    response = await api.get(
        "/api/v1/patients", params={"scope": "all", **params}, headers=persona_headers(user)
    )
    return {i["id"] for i in response.json()["items"]}


async def _actions(session: AsyncSession) -> list[str]:
    return [e.action for e in await session.scalars(select(AuditLog).order_by(AuditLog.id))]


async def test_provider_changes_status_and_it_is_audited(
    api: httpx2.AsyncClient, db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    provider = await add_user(db_session, "provider")
    patient = await create_patient(db_session, field_cipher)

    response = await _act(api, provider, patient, "status", status="inactive")

    assert response.status_code == 200
    assert (response.json()["status"], response.json()["version"]) == ("inactive", 2)
    assert "status_change" in await _actions(db_session)
    assert str(patient.id) in await _list_ids(api, provider, status="inactive")


async def test_deceased_can_be_corrected(
    api: httpx2.AsyncClient, db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    provider = await add_user(db_session, "provider")
    patient = await create_patient(db_session, field_cipher)
    await _act(api, provider, patient, "status", status="deceased")

    corrected = await _act(api, provider, patient, "status", status="active", base_version=2)

    assert corrected.json()["status"] == "active"


async def test_setting_the_same_status_changes_nothing(
    api: httpx2.AsyncClient, db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    provider = await add_user(db_session, "provider")
    patient = await create_patient(db_session, field_cipher)

    response = await _act(api, provider, patient, "status", status="active")

    assert (response.status_code, response.json()["version"]) == (200, 1)
    assert await _actions(db_session) == []


@pytest.mark.parametrize(
    ("role", "action", "body"),
    [
        ("nurse", "status", {"status": "inactive"}),
        ("front_desk", "status", {"status": "inactive"}),
        ("provider", "archive", {"reason": "duplicate"}),
        ("provider", "restore", {}),
    ],
)
async def test_lifecycle_actions_are_permission_checked(
    api: httpx2.AsyncClient,
    db_session: AsyncSession,
    field_cipher: FieldCipher,
    role: str,
    action: str,
    body: dict[str, Any],
) -> None:
    patient = await create_patient(db_session, field_cipher)

    response = await _act(api, await add_user(db_session, role), patient, action, **body)

    assert response.status_code == 403


async def test_archive_hides_from_lists_but_not_from_direct_view_and_restore_undoes_it(
    api: httpx2.AsyncClient, db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    admin = await add_user(db_session, "admin")
    patient = await create_patient(db_session, field_cipher)

    archived = await _act(api, admin, patient, "archive", reason="duplicate")

    assert archived.status_code == 200
    assert (archived.json()["archived"], archived.json()["archive_reason"]) == (True, "duplicate")
    assert (await db_session.get(Patient, patient.id)).archived_by == admin.id  # type: ignore[union-attr]
    assert str(patient.id) not in await _list_ids(api, admin)
    viewed = await api.get(f"/api/v1/patients/{patient.id}", headers=persona_headers(admin))
    assert viewed.status_code == 200

    restored = await _act(api, admin, patient, "restore", base_version=2)

    assert (restored.json()["archived"], restored.json()["archive_reason"]) == (False, None)
    assert str(patient.id) in await _list_ids(api, admin)
    assert [a for a in await _actions(db_session) if a != "view"] == ["archive", "restore"]


async def test_archive_and_restore_reject_the_wrong_state(
    api: httpx2.AsyncClient, db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    admin = await add_user(db_session, "admin")
    patient = await create_patient(db_session, field_cipher)

    not_archived = await _act(api, admin, patient, "restore")
    await _act(api, admin, patient, "archive", reason="other")
    twice = await _act(api, admin, patient, "archive", reason="other", base_version=2)

    for response in (not_archived, twice):
        assert response.status_code == 409
        assert response.json()["code"] == "INVALID_STATE"


@pytest.mark.parametrize(
    ("role", "action", "body"),
    [
        ("provider", "status", {"status": "inactive"}),
        ("admin", "archive", {"reason": "duplicate"}),
    ],
)
async def test_stale_versions_are_refused(
    api: httpx2.AsyncClient,
    db_session: AsyncSession,
    field_cipher: FieldCipher,
    role: str,
    action: str,
    body: dict[str, Any],
) -> None:
    patient = await create_patient(db_session, field_cipher)

    response = await _act(
        api, await add_user(db_session, role), patient, action, base_version=7, **body
    )

    assert response.status_code == 409
    assert response.json()["code"] == "VERSION_CONFLICT"
    assert response.json()["current"]["version"] == 1


@pytest.mark.parametrize(
    ("action", "body"),
    [("status", {"status": "asleep"}), ("archive", {"reason": "bored"})],
)
async def test_unknown_values_are_a_422(
    api: httpx2.AsyncClient,
    db_session: AsyncSession,
    field_cipher: FieldCipher,
    action: str,
    body: dict[str, Any],
) -> None:
    patient = await create_patient(db_session, field_cipher)

    response = await _act(api, await add_user(db_session, "admin"), patient, action, **body)

    assert response.status_code == 422


async def test_a_failed_audit_write_rolls_back_the_action(
    api: httpx2.AsyncClient,
    db_session: AsyncSession,
    field_cipher: FieldCipher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = await add_user(db_session, "admin")
    patient = await create_patient(db_session, field_cipher)

    async def broken(*_: object, **__: object) -> None:
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(Audit, "record_change", broken)

    response = await _act(api, admin, patient, "archive", reason="duplicate")

    assert response.status_code == 500
    await db_session.refresh(patient)
    assert patient.archived_at is None
