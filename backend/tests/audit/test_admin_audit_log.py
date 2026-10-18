import uuid

import httpx2
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import AuditAction, AuditEntry
from app.db.models import User
from tests.factories import add_user, make_audit, persona_headers

pytestmark = [pytest.mark.db, pytest.mark.anyio]

CANARY = "Zyxcanary"


async def _record(
    session: AsyncSession, actor: User, patient_id: uuid.UUID, **changes: object
) -> None:
    audit = await make_audit(session, actor)
    await audit.record_change(
        AuditEntry(
            AuditAction.UPDATE,
            "patient",
            patient_id,
            patient_id,
            {name: (CANARY, value) for name, value in changes.items()} or None,
        )
    )


async def test_admin_sees_newest_first_with_field_names_but_no_values(
    api: httpx2.AsyncClient, db_session: AsyncSession
) -> None:
    admin, nurse = await add_user(db_session, "admin"), await add_user(db_session, "nurse")
    first, second = uuid.uuid4(), uuid.uuid4()
    await _record(db_session, nurse, first, last_name="Smith")
    await _record(db_session, nurse, second, city="Springfield", phone="555-0100")

    response = await api.get("/api/v1/admin/audit-log", headers=persona_headers(admin))

    assert response.status_code == 200
    items = response.json()["items"]
    assert [i["patient_id"] for i in items] == [str(second), str(first)]
    assert items[0]["changed_fields"] == ["city", "phone"]
    assert CANARY not in response.text


async def test_audit_log_filters_by_patient_and_pages_backwards(
    api: httpx2.AsyncClient, db_session: AsyncSession
) -> None:
    admin, nurse = await add_user(db_session, "admin"), await add_user(db_session, "nurse")
    patient = uuid.uuid4()
    for _ in range(3):
        await _record(db_session, nurse, patient)
    await _record(db_session, nurse, uuid.uuid4())
    headers = persona_headers(admin)

    page = (
        await api.get(
            "/api/v1/admin/audit-log",
            params={"patient_id": str(patient), "limit": 2},
            headers=headers,
        )
    ).json()
    rest = (
        await api.get(
            "/api/v1/admin/audit-log",
            params={"patient_id": str(patient), "before_id": page["next_before_id"]},
            headers=headers,
        )
    ).json()

    assert len(page["items"]) == 2
    assert len(rest["items"]) == 1
    assert rest["next_before_id"] is None


@pytest.mark.parametrize("role", ["provider", "nurse", "front_desk"])
async def test_only_admins_see_the_audit_log(
    api: httpx2.AsyncClient, db_session: AsyncSession, role: str
) -> None:
    user = await add_user(db_session, role)

    response = await api.get("/api/v1/admin/audit-log", headers=persona_headers(user))

    assert response.status_code == 403


async def test_audit_log_filters_by_actor(
    api: httpx2.AsyncClient, db_session: AsyncSession
) -> None:
    admin, nurse, provider = [await add_user(db_session, r) for r in ("admin", "nurse", "provider")]
    await _record(db_session, nurse, uuid.uuid4())
    await _record(db_session, provider, uuid.uuid4())

    response = await api.get(
        "/api/v1/admin/audit-log",
        params={"actor_id": str(nurse.id)},
        headers=persona_headers(admin),
    )

    assert [i["actor_id"] for i in response.json()["items"]] == [str(nurse.id)]
