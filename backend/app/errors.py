from enum import Enum, unique
from http import HTTPStatus


@unique
class ErrorCode(Enum):
    """Clients see the member name (e.g. `NOT_FOUND`) as `code`."""

    VALIDATION_FAILED = (HTTPStatus.UNPROCESSABLE_ENTITY, "The request has invalid fields.")
    BUSINESS_RULE_VIOLATION = (
        HTTPStatus.UNPROCESSABLE_ENTITY,
        "The request breaks a business rule.",
    )
    PERMISSION_DENIED = (HTTPStatus.FORBIDDEN, "You don't have permission to do this.")
    NOT_FOUND = (HTTPStatus.NOT_FOUND, "The resource was not found.")
    METHOD_NOT_ALLOWED = (HTTPStatus.METHOD_NOT_ALLOWED, "This method is not allowed here.")
    CONFLICT = (HTTPStatus.CONFLICT, "The resource has changed.")
    INTERNAL_ERROR = (HTTPStatus.INTERNAL_SERVER_ERROR, "Something went wrong on our side.")
    SERVICE_UNAVAILABLE = (HTTPStatus.SERVICE_UNAVAILABLE, "A dependency is unavailable.")

    def __init__(self, status: HTTPStatus, detail: str) -> None:
        self.status = status
        self.detail = detail


class AppError(Exception):
    """Base for expected errors. `detail` must never contain PHI."""

    code: ErrorCode = ErrorCode.INTERNAL_ERROR

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.code.detail
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
