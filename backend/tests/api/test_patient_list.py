from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx2
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import FieldCipher
from app.db.models import AuditLog, Patient, User
from app.patients.repository import PatientRepository
from tests.factories import (
    add_to_care_team,
    add_user,
    add_visit,
    create_patient,
    persona_headers,
)

pytestmark = [pytest.mark.db, pytest.mark.anyio]

NOW = datetime.now(UTC)


@pytest.fixture
async def me(db_session: AsyncSession) -> User:
    return await add_user(db_session, "provider")


@pytest.fixture
def headers(me: User) -> dict[str, str]:
    return persona_headers(me)


async def _patient(
    session: AsyncSession, cipher: FieldCipher, *, last_visit: datetime | None = None, **kw: Any
) -> Patient:
    patient = await create_patient(session, cipher, **kw)
    if last_visit is not None:
        await PatientRepository(session, cipher).update(patient.id, last_visit_at=last_visit)
    return patient


async def _list(api: httpx2.AsyncClient, headers: dict[str, str], **params: Any) -> Any:
    response = await api.get("/api/v1/patients", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def test_list_returns_a_page_with_computed_fields(
    api: httpx2.AsyncClient,
    db_session: AsyncSession,
    field_cipher: FieldCipher,
    me: User,
    headers: dict[str, str],
) -> None:
    dob = date(NOW.year - 40, 1, 1)
    patient = await _patient(db_session, field_cipher, dob=dob, last_visit=NOW - timedelta(days=10))
    await add_to_care_team(db_session, patient, me, "primary_provider")

    page = await _list(api, headers, scope="all")

    assert (page["total"], page["page"], page["page_size"]) == (1, 1, 20)
    [item] = page["items"]
    assert item["id"] == str(patient.id)
    assert (item["last_name"], item["age"], item["status"]) == ("Smith", 40, "active")
    assert item["on_my_care_team"] is True
    assert item["inactivity_suggested"] is False


async def test_page_size_is_capped(api: httpx2.AsyncClient, headers: dict[str, str]) -> None:
    response = await api.get("/api/v1/patients", params={"page_size": 101}, headers=headers)

    assert response.status_code == 422


async def test_scope_my_returns_only_my_active_care_team(
    api: httpx2.AsyncClient,
    db_session: AsyncSession,
    field_cipher: FieldCipher,
    me: User,
    headers: dict[str, str],
) -> None:
    mine = await _patient(db_session, field_cipher)
    await add_to_care_team(db_session, mine, me)
    await _patient(db_session, field_cipher)

    my_ids = [i["id"] for i in (await _list(api, headers, scope="my"))["items"]]
    all_page = await _list(api, headers, scope="all")

    assert my_ids == [str(mine.id)]
    assert all_page["total"] == 2
    assert {i["on_my_care_team"] for i in all_page["items"]} == {True, False}


async def test_filters_by_todays_visits_status_and_archived(
    api: httpx2.AsyncClient,
    db_session: AsyncSession,
    field_cipher: FieldCipher,
    me: User,
    headers: dict[str, str],
) -> None:
    today = await _patient(db_session, field_cipher)
    await add_visit(db_session, today, me, NOW, "scheduled")
    deceased = await _patient(db_session, field_cipher)
    archived = await _patient(db_session, field_cipher)
    repo = PatientRepository(db_session, field_cipher)
    await repo.update(deceased.id, status="deceased")
    await repo.update(archived.id, archived_at=NOW, archive_reason="duplicate")

    def ids(page: Any) -> set[str]:
        return {i["id"] for i in page["items"]}

    assert ids(await _list(api, headers, scope="all", filter="today_visits")) == {str(today.id)}
    assert ids(await _list(api, headers, scope="all", status="deceased")) == {str(deceased.id)}
    assert str(archived.id) not in ids(await _list(api, headers, scope="all"))
    assert str(archived.id) in ids(await _list(api, headers, scope="all", include_archived=True))


async def test_sorts_by_last_visit_and_age(
    api: httpx2.AsyncClient,
    db_session: AsyncSession,
    field_cipher: FieldCipher,
    headers: dict[str, str],
) -> None:
    old = await _patient(
        db_session, field_cipher, dob=date(1950, 6, 1), last_visit=NOW - timedelta(days=90)
    )
    young = await _patient(db_session, field_cipher, dob=date(2000, 6, 1), last_visit=NOW)
    never = await _patient(db_session, field_cipher, dob=date(1980, 6, 1))

    def ids(page: Any) -> list[str]:
        return [i["id"] for i in page["items"]]

    by_visit = await _list(api, headers, scope="all", sort="last_visit", order="desc")
    youngest_first = await _list(api, headers, scope="all", sort="age", order="asc")
    oldest_first = await _list(api, headers, scope="all", sort="age", order="desc")

    assert ids(by_visit) == [str(young.id), str(old.id), str(never.id)]
    assert ids(youngest_first) == [str(young.id), str(never.id), str(old.id)]
    assert ids(oldest_first) == [str(old.id), str(never.id), str(young.id)]


async def test_inactivity_is_suggested_after_three_years_without_a_visit(
    api: httpx2.AsyncClient,
    db_session: AsyncSession,
    field_cipher: FieldCipher,
    headers: dict[str, str],
) -> None:
    lapsed = await _patient(db_session, field_cipher, last_visit=NOW - timedelta(days=3 * 366))
    await _patient(db_session, field_cipher, last_visit=NOW - timedelta(days=30))

    items = (await _list(api, headers, scope="all"))["items"]

    assert {i["id"]: i["inactivity_suggested"] for i in items}[str(lapsed.id)] is True
    assert sum(i["inactivity_suggested"] for i in items) == 1


async def test_pagination(
    api: httpx2.AsyncClient,
    db_session: AsyncSession,
    field_cipher: FieldCipher,
    headers: dict[str, str],
) -> None:
    for _ in range(5):
        await _patient(db_session, field_cipher)

    second = await _list(api, headers, scope="all", page=2, page_size=2)

    assert (second["total"], len(second["items"])) == (5, 2)


async def test_search_combines_name_prefix_dob_and_filters_without_leaking_terms(
    api: httpx2.AsyncClient,
    db_session: AsyncSession,
    field_cipher: FieldCipher,
    me: User,
    headers: dict[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("DEBUG")
    target = await _patient(db_session, field_cipher, last_name="Zyxcanary", dob=date(1970, 3, 4))
    await add_to_care_team(db_session, target, me)
    await _patient(db_session, field_cipher, last_name="Zyxcanary", dob=date(1971, 3, 4))
    await _patient(db_session, field_cipher, last_name="Other", dob=date(1970, 3, 4))

    response = await api.post(
        "/api/v1/patients/search",
        params={"scope": "my"},
        json={"last_name": "zyxc", "dob": "1970-03-04"},
        headers=headers,
    )

    assert response.status_code == 200
    assert [i["id"] for i in response.json()["items"]] == [str(target.id)]
    assert "zyxc" not in str(response.request.url).casefold()
    assert "zyxc" not in caplog.text.casefold()
    [entry] = await db_session.scalars(select(AuditLog).where(AuditLog.entity == "patient_search"))
    assert entry.changes is None


async def test_search_needs_a_name_or_dob(api: httpx2.AsyncClient, headers: dict[str, str]) -> None:
    response = await api.post(
        "/api/v1/patients/search", json={"first_name": "Ada"}, headers=headers
    )

    assert response.status_code == 422


async def test_lists_are_audited_once_per_request(
    api: httpx2.AsyncClient,
    db_session: AsyncSession,
    field_cipher: FieldCipher,
    me: User,
    headers: dict[str, str],
) -> None:
    for _ in range(3):
        await _patient(db_session, field_cipher)

    await _list(api, headers, scope="all")

    entries = list(await db_session.scalars(select(AuditLog)))
    assert [(e.action, e.entity, e.actor_id) for e in entries] == [("view", "patient_list", me.id)]


async def test_search_by_mrn_alone_ignores_case_and_spacing(
    api: httpx2.AsyncClient,
    db_session: AsyncSession,
    field_cipher: FieldCipher,
    headers: dict[str, str],
) -> None:
    target = await _patient(db_session, field_cipher, mrn="MRN-100004")
    await _patient(db_session, field_cipher, mrn="MRN-100005")

    response = await api.post(
        "/api/v1/patients/search",
        params={"scope": "all"},
        json={"mrn": "  mrn-100004 "},
        headers=headers,
    )

    assert [i["id"] for i in response.json()["items"]] == [str(target.id)]
