from enum import Enum, unique
from http import HTTPStatus
from typing import ClassVar


@unique
class ErrorCode(Enum):
    """Clients see the member name (e.g. `NOT_FOUND`) as `code`."""

    VALIDATION_FAILED = (HTTPStatus.UNPROCESSABLE_ENTITY, "The request has invalid fields.")
    BUSINESS_RULE_VIOLATION = (
        HTTPStatus.UNPROCESSABLE_ENTITY,
        "The request breaks a business rule.",
    )
    NOT_AUTHENTICATED = (HTTPStatus.UNAUTHORIZED, "Pick a persona to continue (demo mode).")
    PERMISSION_DENIED = (HTTPStatus.FORBIDDEN, "You don't have permission to do this.")
    NOT_FOUND = (HTTPStatus.NOT_FOUND, "The resource was not found.")
    PATIENT_NOT_FOUND = (HTTPStatus.NOT_FOUND, "Patient not found.")
    METHOD_NOT_ALLOWED = (HTTPStatus.METHOD_NOT_ALLOWED, "This method is not allowed here.")
    CONFLICT = (HTTPStatus.CONFLICT, "The resource has changed.")
    POSSIBLE_DUPLICATE = (
        HTTPStatus.CONFLICT,
        "A patient with this last name and date of birth may already exist.",
    )
    DUPLICATE_MRN = (HTTPStatus.CONFLICT, "Another patient already has this MRN.")
    VERSION_CONFLICT = (HTTPStatus.CONFLICT, "Someone else changed this record first.")
    NOT_NOTE_AUTHOR = (HTTPStatus.FORBIDDEN, "Only the note's author can do this.")
    NOTE_FINALIZED = (
        HTTPStatus.CONFLICT,
        "This note is finalized; it can't be edited or deleted.",
    )
    INVALID_STATE = (
        HTTPStatus.CONFLICT,
        "That action doesn't apply to the record's current state.",
    )
    INTERNAL_ERROR = (HTTPStatus.INTERNAL_SERVER_ERROR, "Something went wrong on our side.")
    SERVICE_UNAVAILABLE = (HTTPStatus.SERVICE_UNAVAILABLE, "A dependency is unavailable.")

    def __init__(self, status: HTTPStatus, detail: str) -> None:
        self.status = status
        self.detail = detail


class AppError(Exception):
    """Base for expected errors. `detail` must never contain PHI."""

    code: ErrorCode = ErrorCode.INTERNAL_ERROR
    headers: ClassVar[dict[str, str]] = {}

    def __init__(self, detail: str | None = None, **extensions: object) -> None:
        self.detail = detail or self.code.detail
        # Extra Problem Details members (RFC 9457 allows them). Never PHI.
        self.extensions = extensions
        super().__init__(self.code.name)


class NotFoundError(AppError):
    code = ErrorCode.NOT_FOUND


class PermissionDeniedError(AppError):
    code = ErrorCode.PERMISSION_DENIED


class ConflictError(AppError):
    code = ErrorCode.CONFLICT


class BusinessRuleError(AppError):
    code = ErrorCode.BUSINESS_RULE_VIOLATION


class ServiceUnavailableError(AppError):
    code = ErrorCode.SERVICE_UNAVAILABLE


class NotAuthenticatedError(AppError):
    code = ErrorCode.NOT_AUTHENTICATED
    # HTTP requires a 401 to name the scheme; ours is the demo persona header.
    headers: ClassVar[dict[str, str]] = {"WWW-Authenticate": 'Persona realm="demo"'}


class PatientNotFoundError(AppError):
    code = ErrorCode.PATIENT_NOT_FOUND


class PossibleDuplicateError(AppError):
    code = ErrorCode.POSSIBLE_DUPLICATE


class DuplicateMrnConflictError(AppError):
    code = ErrorCode.DUPLICATE_MRN


class VersionConflictError(AppError):
    code = ErrorCode.VERSION_CONFLICT


class InvalidStateError(AppError):
    code = ErrorCode.INVALID_STATE


class NotNoteAuthorError(AppError):
    code = ErrorCode.NOT_NOTE_AUTHOR


class NoteFinalizedError(AppError):
    code = ErrorCode.NOTE_FINALIZED
