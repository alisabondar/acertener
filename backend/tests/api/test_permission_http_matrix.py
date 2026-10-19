import uuid

import httpx2
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import Permission
from app.crypto import FieldCipher
from tests.auth.test_permissions import EXPECTED, ROLES
from tests.factories import add_user, create_patient, persona_headers

# One real endpoint guarded by each permission. Bodies are empty on purpose: a permitted role gets
# past the permission check (and then a 422 or 404), a refused one gets a 403 before validation.
ENDPOINTS: dict[str, tuple[str, str]] = {
    "VIEW_DEMOGRAPHICS": ("GET", "/patients/{patient}"),
    "EDIT_DEMOGRAPHICS": ("PATCH", "/patients/{patient}"),
    "CREATE_PATIENT": ("POST", "/patients"),
    "VIEW_CLINICAL": ("GET", "/patients/{patient}/notes"),
    "WRITE_NOTES_AND_VITALS": ("POST", "/patients/{patient}/vitals"),
    "EDIT_ALLERGIES": ("POST", "/patients/{patient}/allergies"),
    "EDIT_CONDITIONS": ("POST", "/patients/{patient}/conditions"),
    "SCHEDULE_VISITS": ("GET", "/visits/today"),
    "CHANGE_PATIENT_STATUS": ("POST", "/patients/{patient}/status"),
    "ARCHIVE_PATIENT": ("POST", "/patients/{patient}/archive"),
    "DELETE_OWN_NOTE": ("DELETE", "/notes/{note}"),
    "VIEW_PATIENT_ACCESS_LOG": ("GET", "/patients/{patient}/access-log"),
    "VIEW_AUDIT_LOG": ("GET", "/admin/audit-log"),
}


def test_every_permission_has_an_endpoint() -> None:
    assert set(ENDPOINTS) == set(Permission.__members__)


@pytest.mark.db
@pytest.mark.anyio
@pytest.mark.parametrize("letter", ROLES)
@pytest.mark.parametrize("permission", EXPECTED)
async def test_each_role_gets_the_status_code_the_spec_allows(
    api: httpx2.AsyncClient,
    db_session: AsyncSession,
    field_cipher: FieldCipher,
    permission: str,
    letter: str,
) -> None:
    user = await add_user(db_session, ROLES[letter])
    patient = await create_patient(db_session, field_cipher)
    method, path = ENDPOINTS[permission]
    url = "/api/v1" + path.format(patient=patient.id, note=uuid.uuid4())
    body: dict[str, object] | None = {} if method in ("POST", "PATCH") else None

    response = await api.request(method, url, json=body, headers=persona_headers(user))

    if letter in EXPECTED[permission]:
        assert response.status_code not in (401, 403), response.text
    else:
        assert response.status_code == 403, response.text
        assert response.json()["code"] == "PERMISSION_DENIED"
