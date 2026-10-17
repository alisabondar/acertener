from collections.abc import Awaitable, Callable
from enum import StrEnum

from app.auth.identity import CurrentUser
from app.db.models import User
from app.errors import PermissionDeniedError

PROVIDER, NURSE, FRONT_DESK, ADMIN = "provider", "nurse", "front_desk", "admin"


class Permission(StrEnum):
    VIEW_DEMOGRAPHICS = "VIEW_DEMOGRAPHICS"
    EDIT_DEMOGRAPHICS = "EDIT_DEMOGRAPHICS"
    CREATE_PATIENT = "CREATE_PATIENT"
    VIEW_CLINICAL = "VIEW_CLINICAL"
    WRITE_NOTES_AND_VITALS = "WRITE_NOTES_AND_VITALS"
    EDIT_ALLERGIES = "EDIT_ALLERGIES"
    EDIT_CONDITIONS = "EDIT_CONDITIONS"
    SCHEDULE_VISITS = "SCHEDULE_VISITS"
    CHANGE_PATIENT_STATUS = "CHANGE_PATIENT_STATUS"
    ARCHIVE_PATIENT = "ARCHIVE_PATIENT"
    # The role may delete notes; "only your own" is checked against the note itself.
    DELETE_OWN_NOTE = "DELETE_OWN_NOTE"
    VIEW_PATIENT_ACCESS_LOG = "VIEW_PATIENT_ACCESS_LOG"
    VIEW_AUDIT_LOG = "VIEW_AUDIT_LOG"


# Deny by default: a role or permission missing here grants nothing.
MATRIX: dict[Permission, frozenset[str]] = {
    Permission.VIEW_DEMOGRAPHICS: frozenset({PROVIDER, NURSE, FRONT_DESK, ADMIN}),
    Permission.EDIT_DEMOGRAPHICS: frozenset({PROVIDER, NURSE, FRONT_DESK}),
    Permission.CREATE_PATIENT: frozenset({PROVIDER, NURSE, FRONT_DESK}),
    Permission.VIEW_CLINICAL: frozenset({PROVIDER, NURSE}),
    Permission.WRITE_NOTES_AND_VITALS: frozenset({PROVIDER, NURSE}),
    Permission.EDIT_ALLERGIES: frozenset({PROVIDER, NURSE}),
    Permission.EDIT_CONDITIONS: frozenset({PROVIDER}),
    Permission.SCHEDULE_VISITS: frozenset({PROVIDER, NURSE, FRONT_DESK}),
    Permission.CHANGE_PATIENT_STATUS: frozenset({PROVIDER, ADMIN}),
    Permission.ARCHIVE_PATIENT: frozenset({ADMIN}),
    Permission.DELETE_OWN_NOTE: frozenset({PROVIDER, NURSE}),
    Permission.VIEW_PATIENT_ACCESS_LOG: frozenset({PROVIDER, NURSE, ADMIN}),
    Permission.VIEW_AUDIT_LOG: frozenset({ADMIN}),
}


def has_permission(user: User, permission: Permission) -> bool:
    return user.role in MATRIX.get(permission, frozenset())


def permissions_for(user: User) -> list[Permission]:
    return sorted(p for p in Permission if has_permission(user, p))


def require(permission: Permission) -> Callable[[User], Awaitable[User]]:
    """A dependency that resolves the current user (401) and then checks the role (403)."""

    async def dependency(user: CurrentUser) -> User:
        if not has_permission(user, permission):
            raise PermissionDeniedError
        return user

    return dependency
