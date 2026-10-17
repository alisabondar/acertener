import json
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import Permission, require
from app.db.models import AuditLog, User
from app.db.session import get_session

router = APIRouter(prefix="/admin", tags=["admin"])


class AuditItemOut(BaseModel):
    id: int
    occurred_at: datetime
    actor_id: uuid.UUID
    via_demo_persona: bool
    action: str
    entity: str
    entity_id: uuid.UUID | None
    patient_id: uuid.UUID | None
    request_id: str | None
    changed_fields: list[str]


class AuditPage(BaseModel):
    items: list[AuditItemOut]
    next_before_id: int | None


def _item(row: AuditLog) -> AuditItemOut:
    # Field names only: admins have no clinical access, so old/new values stay hidden.
    changed = sorted(json.loads(row.changes)) if row.changes else []
    return AuditItemOut(
        id=row.id,
        occurred_at=row.occurred_at,
        actor_id=row.actor_id,
        via_demo_persona=row.via_demo_persona,
        action=row.action,
        entity=row.entity,
        entity_id=row.entity_id,
        patient_id=row.patient_id,
        request_id=row.request_id,
        changed_fields=changed,
    )


@router.get("/audit-log")
async def audit_log(
    _: Annotated[User, Depends(require(Permission.VIEW_AUDIT_LOG))],
    session: Annotated[AsyncSession, Depends(get_session)],
    patient_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    before_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AuditPage:
    """Newest first. Page backwards with `before_id` = the previous page's `next_before_id`."""
    query = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if patient_id is not None:
        query = query.where(AuditLog.patient_id == patient_id)
    if actor_id is not None:
        query = query.where(AuditLog.actor_id == actor_id)
    if before_id is not None:
        query = query.where(AuditLog.id < before_id)
    rows = list(await session.scalars(query))
    return AuditPage(
        items=[_item(r) for r in rows],
        next_before_id=rows[-1].id if len(rows) == limit else None,
    )
