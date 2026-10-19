import json
import logging
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from fastapi import BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.identity import CurrentUser
from app.db.models import AuditLog, User
from app.db.session import DbSession

logger = logging.getLogger("app.audit")


class AuditAction(StrEnum):
    VIEW = "view"
    CREATE = "create"
    UPDATE = "update"
    STATUS_CHANGE = "status_change"
    ARCHIVE = "archive"
    RESTORE = "restore"
    DELETE = "delete"
    ACCESS_DENIED = "access_denied"
    LLM_PAYLOAD_BLOCKED = "llm_payload_blocked"


@dataclass(frozen=True)
class AuditEntry:
    action: AuditAction
    entity: str
    entity_id: uuid.UUID | None = None
    patient_id: uuid.UUID | None = None
    changes: Mapping[str, tuple[object, object]] | None = None  # field -> (old, new)


def build_row(actor: User, entry: AuditEntry, request_id: str | None) -> AuditLog:
    changes = None
    if entry.changes:
        changes = json.dumps(
            {name: {"old": old, "new": new} for name, (old, new) in sorted(entry.changes.items())},
            default=str,
        )
    return AuditLog(
        actor_id=actor.id,
        # Every identity is a demo persona until real login exists.
        via_demo_persona=True,
        action=entry.action,
        entity=entry.entity,
        entity_id=entry.entity_id,
        patient_id=entry.patient_id,
        request_id=request_id,
        changes=changes,
    )


def changed_fields(row: AuditLog) -> list[str]:
    """Names of the fields an entry changed. Never the values, which can be PHI."""
    return sorted(json.loads(row.changes)) if row.changes else []


async def write_now(sessionmaker: async_sessionmaker[AsyncSession], row: AuditLog) -> None:
    """Write one entry in its own transaction."""
    async with sessionmaker() as session:
        session.add(row)
        await session.commit()


async def write_in_background(
    sessionmaker: async_sessionmaker[AsyncSession], row: AuditLog
) -> None:
    """Background writes run after the response, so a failure is logged, never raised.

    Only IDs and the exception type are logged: driver messages can include connection details.
    """
    try:
        await write_now(sessionmaker, row)
    except Exception as exc:
        logger.error(
            "audit_write_failed",
            extra={
                "ctx": {
                    "request_id": row.request_id,
                    "action": row.action,
                    "exc_type": type(exc).__name__,
                }
            },
        )


class Audit:
    """Changes join the caller's transaction; reads are written after the response."""

    def __init__(
        self,
        user: User,
        session: AsyncSession,
        background: BackgroundTasks,
        sessionmaker: async_sessionmaker[AsyncSession],
        request_id: str | None = None,
    ) -> None:
        self._user = user
        self._session = session
        self._background = background
        self._request_id = request_id
        self._sessionmaker = sessionmaker

    async def record_change(self, entry: AuditEntry) -> None:
        self._session.add(build_row(self._user, entry, self._request_id))
        await self._session.flush()

    def record_read(self, entry: AuditEntry) -> None:
        row = build_row(self._user, entry, self._request_id)
        self._background.add_task(write_in_background, self._sessionmaker, row)


async def get_audit(
    request: Request,
    user: CurrentUser,
    session: DbSession,
    background: BackgroundTasks,
) -> Audit:
    return Audit(
        user,
        session,
        background,
        request.app.state.sessionmaker,
        request_id=getattr(request.state, "request_id", None),
    )
