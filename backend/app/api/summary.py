import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, cast
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.deidentify import build_context
from app.ai.gateway import Gateway
from app.ai.leak_check import leak_check
from app.ai.summary import SummaryService, SummaryState, chart_inputs, generate
from app.audit import Audit, AuditAction, AuditEntry, get_audit
from app.auth.permissions import Permission, require
from app.db.models import User
from app.db.session import DbSession
from app.errors import NotFoundError, RateLimitedError
from app.patients.derived import age_on
from app.patients.queries import practice_today
from app.schemas.clinical import Severity
from app.schemas.summary import (
    LeakCheckOut,
    PayloadPreview,
    SummaryAllergy,
    SummaryCondition,
    SummaryHeader,
    SummaryOut,
    SummaryStatus,
)

router = APIRouter(tags=["summary"])

Clinician = Annotated[User, Depends(require(Permission.VIEW_CLINICAL))]
AuditDep = Annotated[Audit, Depends(get_audit)]

# "Refresh now" is allowed once per this many seconds per patient.
MANUAL_REFRESH_SECONDS = 10


def get_gateway(request: Request) -> Gateway:
    gateway: Gateway = request.app.state.gateway
    return gateway


GatewayDep = Annotated[Gateway, Depends(get_gateway)]


def _service(request: Request, session: AsyncSession) -> SummaryService:
    seconds = request.app.state.settings.summary_debounce_seconds
    return SummaryService(session, timedelta(seconds=seconds))


async def _run_generation(
    request: Request, gateway: Gateway, user: User, patient_id: uuid.UUID
) -> None:
    async with request.app.state.sessionmaker() as session:
        audit = Audit(user, session, BackgroundTasks(), request.app.state.sessionmaker)
        await generate(session, gateway, audit, patient_id)


async def _out(
    request: Request, service: SummaryService, patient_id: uuid.UUID, state: SummaryState
) -> SummaryOut:
    patient, allergies, conditions = await service.header(patient_id)
    today = practice_today(
        datetime.now(UTC), ZoneInfo(request.app.state.settings.practice_timezone)
    )
    row = state.row
    narrative = row.content if row and row.status in ("fresh", "stale", "generating") else None
    return SummaryOut(
        header=SummaryHeader(
            first_name=patient.first_name,
            last_name=patient.last_name,
            age=age_on(patient.dob, today),
            allergies=[
                SummaryAllergy(substance=a.substance, severity=cast(Severity | None, a.severity))
                for a in allergies
            ],
            conditions=[SummaryCondition(icd10_code=c.icd10_code, name=c.name) for c in conditions],
        ),
        status=cast(SummaryStatus, row.status) if row else "stale",
        narrative=narrative,
        is_ai_generated=narrative is not None,
        provider=row.model if row and narrative else None,
        generated_at=row.generated_at if row else None,
        next_refresh_at=state.next_refresh_at,
        error_code=row.error_code if row and row.status in ("failed", "blocked") else None,
    )


@router.get("/patients/{patient_id}/summary")
async def get_summary(
    request: Request,
    patient_id: uuid.UUID,
    user: Clinician,
    session: DbSession,
    audit: AuditDep,
    gateway: GatewayDep,
    background: BackgroundTasks,
) -> SummaryOut:
    service = _service(request, session)
    state = await service.view(patient_id)
    if state.claimed:
        background.add_task(_run_generation, request, gateway, user, patient_id)
    audit.record_read(AuditEntry(AuditAction.VIEW, "patient_summary", patient_id, patient_id))
    return await _out(request, service, patient_id, state)


@router.post("/patients/{patient_id}/summary/refresh", status_code=202)
async def refresh_summary(
    request: Request,
    response: Response,
    patient_id: uuid.UUID,
    user: Clinician,
    session: DbSession,
    gateway: GatewayDep,
    background: BackgroundTasks,
) -> SummaryOut:
    last: dict[uuid.UUID, float] = request.app.state.summary_refreshes
    wait = MANUAL_REFRESH_SECONDS - (time.monotonic() - last.get(patient_id, float("-inf")))
    if wait > 0:
        raise RateLimitedError(retry_after=int(wait) + 1)
    now = time.monotonic()
    # Forget patients whose window has passed, so this stays small in a long-running process.
    for stale in [pid for pid, at in last.items() if now - at >= MANUAL_REFRESH_SECONDS]:
        del last[stale]
    last[patient_id] = now
    service = _service(request, session)
    if await service.claim_now(patient_id):
        background.add_task(_run_generation, request, gateway, user, patient_id)
    return await _out(request, service, patient_id, await service.view(patient_id))


@router.get("/dev/patients/{patient_id}/ai-payload")
async def preview_payload(
    request: Request,
    patient_id: uuid.UUID,
    user: Clinician,
    session: DbSession,
    audit: AuditDep,
    gateway: GatewayDep,
) -> PayloadPreview:
    """Exactly what would be sent to the AI, and the leak check's verdict, without sending it."""
    if not request.app.state.settings.demo_mode:
        raise NotFoundError
    ids, records = await chart_inputs(session, patient_id)
    tz = request.app.state.settings.practice_timezone
    context = build_context(ids, records, practice_today(datetime.now(UTC), ZoneInfo(tz)))
    verdict = leak_check(context.model_dump_json(), ids, context.clinical_terms())
    audit.record_read(AuditEntry(AuditAction.VIEW, "ai_payload_preview", patient_id, patient_id))
    payload: dict[str, Any] = context.model_dump(mode="json")
    return PayloadPreview(
        payload=payload,
        leak_check=LeakCheckOut(ok=verdict.ok, detectors=list(verdict.detectors)),
        provider=gateway.provider.name,
    )
