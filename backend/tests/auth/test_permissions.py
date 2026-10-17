import pytest

from app.auth.permissions import Permission, has_permission, permissions_for
from app.db.models import User

ROLES = {"P": "provider", "N": "nurse", "F": "front_desk", "A": "admin"}

# Written out from the spec's Roles & Permissions table, independently of MATRIX,
# so the test checks the code against the spec rather than against itself.
EXPECTED = {
    "VIEW_DEMOGRAPHICS": "PNFA",
    "EDIT_DEMOGRAPHICS": "PNF",
    "VIEW_CLINICAL": "PN",
    "WRITE_NOTES_AND_VITALS": "PN",
    "EDIT_ALLERGIES": "PN",
    "EDIT_CONDITIONS": "P",
    "CREATE_PATIENT": "PNF",
    "SCHEDULE_VISITS": "PNF",
    "CHANGE_PATIENT_STATUS": "PA",
    "ARCHIVE_PATIENT": "A",
    "DELETE_OWN_NOTE": "PN",
    "VIEW_PATIENT_ACCESS_LOG": "PNA",
    "VIEW_AUDIT_LOG": "A",
}


def test_every_permission_has_an_expected_row() -> None:
    assert set(EXPECTED) == set(Permission.__members__)


@pytest.mark.parametrize("letter", ROLES)
@pytest.mark.parametrize("permission", EXPECTED)
def test_permission_matrix_matches_the_spec(permission: str, letter: str) -> None:
    user = User(role=ROLES[letter])

    assert has_permission(user, Permission[permission]) is (letter in EXPECTED[permission])


def test_unknown_roles_get_nothing() -> None:
    assert permissions_for(User(role="intern")) == []
