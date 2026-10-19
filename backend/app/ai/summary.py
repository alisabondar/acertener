"""A patient's AI summary: cached, regenerated lazily after clinical changes settle.

A view never waits on the AI. If the summary is stale and the last change is older than the
debounce, the view claims the row (one atomic UPDATE, so concurrent viewers start at most one
generation) and generation runs in the background. Summaries are only generated for charts
someone is looking at, which keeps a free-tier quota from being spent on 10k idle patients.
"""

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.deidentify import (
    ChartRecords,
    ConditionRecord,
    NoteRecord,
    VisitRecord,
    VitalsRecord,
    build_context,
)
from app.ai.gateway import SYSTEM_PROMPT, Blocked, Gateway, RateLimited, Summary
from app.ai.identifiers import PatientIdentifiers
from app.ai.payload import DeidentifiedClinicalContext
from app.audit import Audit, AuditAction, AuditEntry
from app.db.models import Allergy, Condition, Note, Patient, PatientSummary, User, Visit, Vital
from app.errors import PatientNotFoundError

logger = logging.getLogger("app.ai")

# A generation that hasn't finished by now (the process died mid-request) may be retried.
STUCK_AFTER = timedelta(seconds=60)


@dataclass(frozen=True)
class SummaryState:
    row: PatientSummary | None
    claimed: bool
    next_refresh_at: datetime | None


def _now() -> datetime:
    return datetime.now(UTC)


async def chart_inputs(
    session: AsyncSession, patient_id: uuid.UUID
) -> tuple[PatientIdentifiers, ChartRecords]:
    """Everything the de-identifier needs about one patient (and which staff names to remove)."""
    patient = await session.get(Patient, patient_id)
    if patient is None:
        raise PatientNotFoundError
    staff = tuple((await session.scalars(select(User.name))).all())
    ids = PatientIdentifiers(
        patient_id=patient.id,
        first_name=patient.first_name,
        last_name=patient.last_name,
        mrn=patient.mrn,
        dob=patient.dob,
        phone=patient.phone,
        email=patient.email,
        address_line1=patient.address_line1,
        address_line2=patient.address_line2,
        city=patient.city,
        postal_code=patient.postal_code,
        staff_names=staff,
    )
    visits = await session.scalars(select(Visit).where(Visit.patient_id == patient_id))
    notes = await session.scalars(
        select(Note).where(Note.patient_id == patient_id, Note.deleted_at.is_(None))
    )
    vitals = await session.scalars(select(Vital).where(Vital.patient_id == patient_id))
    conditions = await session.scalars(select(Condition).where(Condition.patient_id == patient_id))
    records = ChartRecords(
        sex=patient.gender,
        visits=[VisitRecord(v.scheduled_at, v.reason, v.status) for v in visits],
        notes=[NoteRecord(n.encounter_at, n.content, n.status == "final") for n in notes],
        vitals=[
            VitalsRecord(
                v.taken_at,
                v.bp_systolic,
                v.bp_diastolic,
                v.heart_rate,
                v.respiratory_rate,
                v.spo2,
                v.temperature_c,
                v.weight_kg,
                v.height_cm,
            )
            for v in vitals
        ],
        conditions=[ConditionRecord(c.icd10_code, c.name, c.status) for c in conditions],
    )
    return ids, records


def payload_hash(context: DeidentifiedClinicalContext, model: str) -> str:
    """Same payload, model, and prompt means the same narrative, so it can be reused."""
    key = f"{model}\n{SYSTEM_PROMPT}\n{context.model_dump_json()}"
    return hashlib.sha256(key.encode()).hexdigest()


class SummaryService:
    def __init__(self, session: AsyncSession, debounce: timedelta) -> None:
        self._session = session
        self._debounce = debounce

    async def header(self, patient_id: uuid.UUID) -> tuple[list[Allergy], list[Condition]]:
        allergies = await self._session.scalars(
            select(Allergy).where(Allergy.patient_id == patient_id, Allergy.status == "active")
        )
        conditions = await self._session.scalars(
            select(Condition).where(
                Condition.patient_id == patient_id, Condition.status == "active"
            )
        )
        return list(allergies), list(conditions)

    async def view(self, patient_id: uuid.UUID) -> SummaryState:
        """The cached summary, claiming a background generation if it's due."""
        if await self._session.get(Patient, patient_id) is None:
            raise PatientNotFoundError
        now = _now()
        row = await self._row(patient_id)
        if row is None:
            claimed = await self._claim_new(patient_id, now)
        elif row.status in ("stale", "generating"):
            due = row.source_changed_at is None or now - row.source_changed_at >= self._debounce
            claimed = due and await self._claim(patient_id, now)
        else:
            claimed = False
        row = await self._row(patient_id)
        next_refresh = None
        if row and row.status == "stale" and row.source_changed_at:
            next_refresh = row.source_changed_at + self._debounce
        return SummaryState(row, claimed, next_refresh)

    async def claim_now(self, patient_id: uuid.UUID) -> bool:
        """For "Refresh now": skip the debounce (one generation still runs at a time)."""
        if await self._session.get(Patient, patient_id) is None:
            raise PatientNotFoundError
        now = _now()
        if await self._row(patient_id) is None:
            return await self._claim_new(patient_id, now)
        result = await self._session.execute(
            update(PatientSummary)
            .where(
                PatientSummary.patient_id == patient_id,
                or_(
                    PatientSummary.status != "generating",
                    PatientSummary.generation_started_at < now - STUCK_AFTER,
                ),
            )
            .values(status="generating", generation_started_at=now)
            .returning(PatientSummary.patient_id)
        )
        await self._session.commit()
        return result.first() is not None

    async def _row(self, patient_id: uuid.UUID) -> PatientSummary | None:
        return await self._session.get(PatientSummary, patient_id, populate_existing=True)

    async def _claim(self, patient_id: uuid.UUID, now: datetime) -> bool:
        result = await self._session.execute(
            update(PatientSummary)
            .where(
                PatientSummary.patient_id == patient_id,
                or_(
                    PatientSummary.status == "stale",
                    (PatientSummary.status == "generating")
                    & (PatientSummary.generation_started_at < now - STUCK_AFTER),
                ),
            )
            .values(status="generating", generation_started_at=now)
            .returning(PatientSummary.patient_id)
        )
        await self._session.commit()
        return result.first() is not None

    async def _claim_new(self, patient_id: uuid.UUID, now: datetime) -> bool:
        result = await self._session.execute(
            insert(PatientSummary)
            .values(patient_id=patient_id, status="generating", generation_started_at=now)
            .on_conflict_do_nothing()
            .returning(PatientSummary.patient_id)
        )
        await self._session.commit()
        return result.first() is not None


async def generate(
    session: AsyncSession, gateway: Gateway, audit: Audit, patient_id: uuid.UUID
) -> None:
    """Build the payload, send it through the gateway, and store the outcome.

    Never leaves a summary stuck "generating": anything unexpected ends as failed (Retry).
    """
    try:
        await _generate(session, gateway, audit, patient_id)
    except Exception as exc:
        # The type only: exception messages can carry chart data.
        logger.error("summary_generation_crashed", extra={"ctx": {"error": type(exc).__name__}})
        await session.rollback()
        await session.execute(
            update(PatientSummary)
            .where(PatientSummary.patient_id == patient_id)
            .values(status="failed", error_code="internal_error", generation_started_at=None)
        )
        await session.commit()


async def _generate(
    session: AsyncSession, gateway: Gateway, audit: Audit, patient_id: uuid.UUID
) -> None:
    started = _now()
    ids, records = await chart_inputs(session, patient_id)
    context = build_context(ids, records, started.date())
    digest = payload_hash(context, gateway.provider.model)
    row = await session.get(PatientSummary, patient_id, populate_existing=True)
    if row is None:
        return

    if row.input_hash == digest and row.content:
        # Nothing the AI would see has changed: keep the narrative, skip the call.
        values: dict[str, object] = {"status": "fresh", "error_code": None}
    else:
        result = await gateway.summarize(context, ids)
        values = {"input_hash": digest}
        if isinstance(result, Summary):
            values |= {
                "status": "fresh",
                "content": result.narrative,
                "model": result.provider,
                "generated_at": _now(),
                "error_code": None,
            }
        elif isinstance(result, Blocked):
            values |= {"status": "blocked", "content": None, "error_code": "blocked"}
            await audit.record_change(
                AuditEntry(
                    AuditAction.LLM_PAYLOAD_BLOCKED,
                    "patient_summary",
                    patient_id,
                    patient_id,
                    # Which detectors fired and where; never what they matched.
                    {"detectors": (None, list(result.detectors)), "stage": (None, result.stage)},
                )
            )
        elif isinstance(result, RateLimited):
            # Try again once the provider's window reopens.
            values |= {
                "status": "stale",
                "error_code": "rate_limited",
                "source_changed_at": _now() + timedelta(seconds=result.retry_after),
            }
            values.pop("input_hash")
        else:
            values |= {"status": "failed", "content": None, "error_code": result.error_code}

    # A change that arrived while we were generating makes this result stale on arrival.
    await session.refresh(row)
    if (
        row.source_changed_at
        and row.source_changed_at > started
        and values.get("status") == "fresh"
    ):
        values["status"] = "stale"
    await session.execute(
        update(PatientSummary)
        .where(PatientSummary.patient_id == patient_id)
        .values(**values, generation_started_at=None)
    )
    await session.commit()
