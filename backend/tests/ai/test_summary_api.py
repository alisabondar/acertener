import asyncio
import json
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx2
import pytest
from fastapi import FastAPI
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai import summary as summary_module
from app.ai.gateway import (
    ALLOWED_HOSTS,
    Failed,
    Gateway,
    GeminiProvider,
    MockProvider,
    RateLimited,
    Result,
    TokenBucket,
)
from app.ai.payload import DeidentifiedClinicalContext
from app.ai.summary import SummaryService, generate
from app.audit import Audit
from app.config import Settings
from app.crypto import FieldCipher
from app.db import create_engine
from app.db.models import AuditLog, Condition, Note, Patient, PatientSummary, User
from app.patients.derived import age_on
from app.patients.queries import practice_today
from tests.factories import add_user, create_patient, make_audit, persona_headers

pytestmark = [pytest.mark.db, pytest.mark.anyio]

Api = httpx2.AsyncClient


class CountingProvider(MockProvider):
    """The mock, counting calls; optionally failing."""

    def __init__(self, fail: str | None = None) -> None:
        self.calls = 0
        self._fail = fail

    async def complete(self, context: DeidentifiedClinicalContext) -> Result:
        self.calls += 1
        return Failed(self._fail) if self._fail else await super().complete(context)


@pytest.fixture
def provider(app: FastAPI) -> CountingProvider:
    counting = CountingProvider()
    app.state.gateway = Gateway(counting, TokenBucket(per_minute=1000))
    return counting


@pytest.fixture
async def doctor(db_session: AsyncSession) -> User:
    return await add_user(db_session, "provider")


@pytest.fixture
async def patient(db_session: AsyncSession, field_cipher: FieldCipher, doctor: User) -> Patient:
    patient = await create_patient(db_session, field_cipher, first_name="Rose", last_name="Oneil")
    db_session.add(
        Condition(
            patient_id=patient.id, icd10_code="I10", name="Hypertension", recorded_by=doctor.id
        )
    )
    db_session.add(
        Note(
            patient_id=patient.id,
            author_id=doctor.id,
            encounter_at=datetime.now(UTC) - timedelta(days=3),
            content="Rose Oneil reports headaches. BP 150/95.",
            status="final",
            finalized_at=datetime.now(UTC),
        )
    )
    await db_session.flush()
    return patient


async def _summary(api: Api, user: User, patient: Patient) -> Any:
    response = await api.get(
        f"/api/v1/patients/{patient.id}/summary", headers=persona_headers(user)
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _set_summary(session: AsyncSession, patient: Patient, **values: Any) -> None:
    session.add(PatientSummary(patient_id=patient.id, **{"status": "stale", **values}))
    await session.flush()


async def test_a_first_view_generates_a_summary_with_a_deterministic_header(
    api: Api, doctor: User, patient: Patient, provider: CountingProvider, settings: Settings
) -> None:
    first = await _summary(api, doctor, patient)
    second = await _summary(api, doctor, patient)

    assert first["status"] == "generating"
    today = practice_today(datetime.now(UTC), ZoneInfo(settings.practice_timezone))
    assert (first["header"]["first_name"], first["header"]["last_name"]) == ("Rose", "Oneil")
    assert first["header"]["age"] == age_on(date(1990, 1, 31), today)
    assert first["header"]["conditions"] == [{"icd10_code": "I10", "name": "Hypertension"}]
    assert second["status"] == "fresh"
    assert "Hypertension" in second["narrative"]
    assert (second["is_ai_generated"], second["provider"]) == (True, "Mock AI")
    assert "Rose" not in second["narrative"]
    assert provider.calls == 1


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 19, 15, 0, tzinfo=UTC)

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    """Frozen time for the summary service; tests move it forward explicitly."""
    frozen = Clock()
    monkeypatch.setattr(summary_module, "_now", lambda: frozen.now)
    return frozen


async def test_a_change_waits_out_the_debounce_then_regenerates(
    api: Api,
    db_session: AsyncSession,
    doctor: User,
    patient: Patient,
    provider: CountingProvider,
    clock: Clock,
) -> None:
    changed_at = clock.now
    await _set_summary(db_session, patient, source_changed_at=changed_at)
    clock.advance(5)

    waiting = await _summary(api, doctor, patient)
    clock.advance(10)
    settled = await _summary(api, doctor, patient)
    after = await _summary(api, doctor, patient)

    assert waiting["status"] == "stale"
    assert datetime.fromisoformat(waiting["next_refresh_at"]) == changed_at + timedelta(seconds=15)
    assert settled["status"] == "generating"
    assert after["status"] == "fresh"
    assert provider.calls == 1


async def test_concurrent_viewers_start_only_one_generation(
    migrated_database: str, field_cipher: FieldCipher
) -> None:
    """Separate connections, viewing at the same moment: the atomic claim lets one through."""
    engine = create_engine(migrated_database)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as setup:
        patient = await create_patient(setup, field_cipher)
        setup.add(
            PatientSummary(
                patient_id=patient.id,
                status="stale",
                source_changed_at=datetime.now(UTC) - timedelta(minutes=1),
            )
        )
        await setup.commit()

    async def view() -> bool:
        async with sessions() as session:
            state = await SummaryService(session, timedelta(seconds=15)).view(patient.id)
            return state.claimed

    try:
        claims = await asyncio.gather(*(view() for _ in range(5)))
        assert claims.count(True) == 1
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(
                delete(PatientSummary).where(PatientSummary.patient_id == patient.id)
            )
            await cleanup.execute(delete(Patient).where(Patient.id == patient.id))
            await cleanup.commit()
        await engine.dispose()


async def test_an_unchanged_chart_reuses_the_cached_narrative(
    api: Api, db_session: AsyncSession, doctor: User, patient: Patient, provider: CountingProvider
) -> None:
    await _summary(api, doctor, patient)
    await db_session.execute(
        update(PatientSummary)
        .where(PatientSummary.patient_id == patient.id)
        .values(status="stale", source_changed_at=datetime.now(UTC) - timedelta(minutes=1))
    )

    await _summary(api, doctor, patient)
    body = await _summary(api, doctor, patient)

    assert body["status"] == "fresh"
    assert provider.calls == 1


async def test_manual_refresh_skips_the_wait_but_is_rate_limited(
    api: Api, db_session: AsyncSession, doctor: User, patient: Patient, provider: CountingProvider
) -> None:
    await _set_summary(db_session, patient, source_changed_at=datetime.now(UTC))
    url = f"/api/v1/patients/{patient.id}/summary/refresh"

    first = await api.post(url, headers=persona_headers(doctor))
    second = await api.post(url, headers=persona_headers(doctor))

    assert first.status_code == 202
    assert provider.calls == 1
    assert second.status_code == 429
    assert int(second.headers["Retry-After"]) > 0


async def test_a_blocked_payload_is_never_sent_and_is_audited_by_detector_only(
    api: Api,
    db_session: AsyncSession,
    field_cipher: FieldCipher,
    doctor: User,
    provider: CountingProvider,
) -> None:
    patient = await create_patient(db_session, field_cipher, mrn="MRN-555123")
    db_session.add(
        Note(
            patient_id=patient.id,
            author_id=doctor.id,
            encounter_at=datetime.now(UTC),
            content="Old chart number 555123 is on file.",
            status="final",
            finalized_at=datetime.now(UTC),
        )
    )
    await db_session.flush()

    await _summary(api, doctor, patient)
    body = await _summary(api, doctor, patient)

    assert (body["status"], body["narrative"]) == ("blocked", None)
    assert provider.calls == 0
    [entry] = await db_session.scalars(
        select(AuditLog).where(AuditLog.action == "llm_payload_blocked")
    )
    assert entry.patient_id == patient.id
    assert "555123" not in (entry.changes or "")


async def test_a_provider_failure_still_returns_the_header(
    api: Api, app: FastAPI, doctor: User, patient: Patient
) -> None:
    app.state.gateway = Gateway(CountingProvider(fail="timeout"), TokenBucket(per_minute=1000))

    await _summary(api, doctor, patient)
    body = await _summary(api, doctor, patient)

    assert (body["status"], body["narrative"], body["error_code"]) == ("failed", None, "timeout")
    assert body["header"]["conditions"]


async def test_editing_a_draft_doesnt_make_the_summary_stale_but_finalizing_does(
    api: Api, db_session: AsyncSession, doctor: User, patient: Patient, provider: CountingProvider
) -> None:
    await _summary(api, doctor, patient)
    await _summary(api, doctor, patient)
    headers = persona_headers(doctor)
    draft = (
        await api.post(
            f"/api/v1/patients/{patient.id}/notes", json={"content": "Draft"}, headers=headers
        )
    ).json()
    await api.patch(
        f"/api/v1/notes/{draft['id']}", json={"content": "Still a draft"}, headers=headers
    )

    after_draft = await _summary(api, doctor, patient)
    await api.post(f"/api/v1/notes/{draft['id']}/finalize", headers=headers)
    after_finalize = await db_session.get(PatientSummary, patient.id, populate_existing=True)

    assert after_draft["status"] == "fresh"
    assert after_finalize is not None
    assert after_finalize.status == "stale"


@pytest.mark.parametrize("role", ["front_desk", "admin"])
async def test_only_clinical_roles_see_the_summary(
    api: Api, db_session: AsyncSession, patient: Patient, role: str
) -> None:
    user = await add_user(db_session, role)

    response = await api.get(
        f"/api/v1/patients/{patient.id}/summary", headers=persona_headers(user)
    )

    assert response.status_code == 403


async def test_the_payload_preview_shows_exactly_what_would_be_sent_without_sending_it(
    api: Api, doctor: User, patient: Patient, provider: CountingProvider
) -> None:
    response = await api.get(
        f"/api/v1/dev/patients/{patient.id}/ai-payload", headers=persona_headers(doctor)
    )

    body = response.json()
    assert response.status_code == 200
    assert body["leak_check"] == {"ok": True, "detectors": []}
    assert body["payload"]["notes"][0]["text"].startswith("[PATIENT] reports headaches")
    assert body["provider"] == "Mock AI"
    assert provider.calls == 0


async def test_the_payload_preview_is_only_for_demo_mode(
    app: FastAPI, api: Api, doctor: User, patient: Patient
) -> None:
    app.state.settings = app.state.settings.model_copy(update={"demo_mode": False})

    response = await api.get(
        f"/api/v1/dev/patients/{patient.id}/ai-payload", headers=persona_headers(doctor)
    )

    assert response.status_code in (401, 404)


async def test_unknown_patients_have_no_summary(api: Api, doctor: User) -> None:
    missing = uuid.uuid4()

    view = await api.get(f"/api/v1/patients/{missing}/summary", headers=persona_headers(doctor))
    refresh = await api.post(
        f"/api/v1/patients/{missing}/summary/refresh", headers=persona_headers(doctor)
    )

    assert (view.status_code, refresh.status_code) == (404, 404)


async def test_refresh_now_works_on_a_chart_nobody_has_opened(
    api: Api, doctor: User, patient: Patient, provider: CountingProvider
) -> None:
    response = await api.post(
        f"/api/v1/patients/{patient.id}/summary/refresh", headers=persona_headers(doctor)
    )

    assert response.status_code == 202
    assert provider.calls == 1


class RateLimitedProvider(MockProvider):
    async def complete(self, context: DeidentifiedClinicalContext) -> Result:
        return RateLimited(retry_after=20)


async def test_a_rate_limited_provider_leaves_the_summary_waiting_to_retry(
    api: Api, app: FastAPI, doctor: User, patient: Patient
) -> None:
    app.state.gateway = Gateway(RateLimitedProvider(), TokenBucket(per_minute=1000))

    await _summary(api, doctor, patient)
    body = await _summary(api, doctor, patient)

    assert body["status"] == "stale"
    assert body["next_refresh_at"] is not None


async def test_a_change_during_generation_leaves_the_result_stale(
    api: Api, app: FastAPI, db_session: AsyncSession, doctor: User, patient: Patient
) -> None:
    class ChangesMidway(MockProvider):
        async def complete(self, context: DeidentifiedClinicalContext) -> Result:
            # Someone records vitals while the AI is still writing.
            await db_session.execute(
                update(PatientSummary)
                .where(PatientSummary.patient_id == patient.id)
                .values(source_changed_at=datetime.now(UTC) + timedelta(seconds=1))
            )
            return await super().complete(context)

    app.state.gateway = Gateway(ChangesMidway(), TokenBucket(per_minute=1000))

    await _summary(api, doctor, patient)
    row = await db_session.get(PatientSummary, patient.id, populate_existing=True)

    assert row is not None
    assert row.status == "stale"
    assert row.content is not None


async def test_generation_without_a_claimed_row_does_nothing(
    db_session: AsyncSession, doctor: User, patient: Patient
) -> None:
    audit: Audit = await make_audit(db_session, doctor)

    await generate(db_session, Gateway(MockProvider()), audit, patient.id)

    assert await db_session.get(PatientSummary, patient.id) is None


async def test_the_payload_preview_404s_for_an_unknown_patient(api: Api, doctor: User) -> None:
    response = await api.get(
        f"/api/v1/dev/patients/{uuid.uuid4()}/ai-payload", headers=persona_headers(doctor)
    )

    assert response.status_code == 404


async def test_a_failure_isnt_relabelled_stale_by_a_change_that_arrived_meanwhile(
    api: Api, app: FastAPI, db_session: AsyncSession, doctor: User, patient: Patient
) -> None:
    class FailsAfterAChange(MockProvider):
        async def complete(self, context: DeidentifiedClinicalContext) -> Result:
            await db_session.execute(
                update(PatientSummary)
                .where(PatientSummary.patient_id == patient.id)
                .values(source_changed_at=datetime.now(UTC) + timedelta(seconds=1))
            )
            return Failed("timeout")

    app.state.gateway = Gateway(FailsAfterAChange(), TokenBucket(per_minute=1000))

    await _summary(api, doctor, patient)
    row = await db_session.get(PatientSummary, patient.id, populate_existing=True)

    assert row is not None
    assert (row.status, row.error_code) == ("failed", "timeout")


async def test_switching_providers_regenerates_instead_of_reusing_the_old_narrative(
    api: Api, app: FastAPI, db_session: AsyncSession, doctor: User, patient: Patient
) -> None:
    class OtherProvider(MockProvider):
        name = "Gemini"
        model = "gemini-2.5-flash"

    await _summary(api, doctor, patient)
    await _summary(api, doctor, patient)
    app.state.gateway = Gateway(OtherProvider(), TokenBucket(per_minute=1000))
    await db_session.execute(
        update(PatientSummary)
        .where(PatientSummary.patient_id == patient.id)
        .values(status="stale", source_changed_at=datetime.now(UTC) - timedelta(minutes=1))
    )

    await _summary(api, doctor, patient)
    body = await _summary(api, doctor, patient)

    assert body["provider"] == "Gemini"


async def test_an_unexpected_error_ends_as_failed_rather_than_stuck_generating(
    api: Api, app: FastAPI, db_session: AsyncSession, doctor: User, patient: Patient
) -> None:
    class Crashes(MockProvider):
        async def complete(self, context: DeidentifiedClinicalContext) -> Result:
            raise RuntimeError("boom")

    app.state.gateway = Gateway(Crashes(), TokenBucket(per_minute=1000))

    await _summary(api, doctor, patient)
    body = await _summary(api, doctor, patient)

    assert (body["status"], body["error_code"]) == ("failed", "internal_error")


@pytest.mark.privacy
async def test_canary_through_the_full_stack_never_leaves_in_an_outbound_byte(
    api: Api, db_session: AsyncSession, field_cipher: FieldCipher, app: FastAPI
) -> None:
    """API → database → de-identifier → leak check → gateway → a recording transport."""
    doctor = await add_user(db_session, "provider", name="Dr. Quill Ashgrove")
    patient = await create_patient(
        db_session,
        field_cipher,
        first_name="Zephyrine",
        last_name="Quorrowby",
        mrn="MRN-771905",
        phone="555-301-7719",
        email="z.quorrowby@example.test",
        city="Wexhollow",
    )
    db_session.add(
        Note(
            patient_id=patient.id,
            author_id=doctor.id,
            encounter_at=datetime.now(UTC) - timedelta(days=2),
            content="Zephyrine Quorrowby (MRN-771905) called from 555-301-7719 about her cough.",
            status="final",
            finalized_at=datetime.now(UTC),
        )
    )
    await db_session.flush()
    sent: list[httpx2.Request] = []

    def record(request: httpx2.Request) -> httpx2.Response:
        assert request.url.host in ALLOWED_HOSTS, request.url.host
        sent.append(request)
        reply = json.dumps({"narrative": "Adult with a cough for a few days."})
        return httpx2.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": reply}]}}]}
        )

    gemini = GeminiProvider(api_key="k", model="m", transport=httpx2.MockTransport(record))
    app.state.gateway = Gateway(gemini, TokenBucket(per_minute=1000))

    await _summary(api, doctor, patient)
    body = await _summary(api, doctor, patient)

    assert body["status"] == "fresh"
    [request] = sent
    outbound = (str(request.url) + str(request.headers) + request.content.decode()).lower()
    for canary in (
        "zephyrine",
        "quorrowby",
        "771905",
        "3017719",
        "301-7719",
        "example.test",
        "wexhollow",
        "ashgrove",
        str(patient.id),
    ):
        assert canary not in outbound, canary
