from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import FieldCipher
from app.patients.repository import DuplicateMrnError, NewPatient, PatientRepository

pytestmark = [pytest.mark.db, pytest.mark.anyio]


def new_patient(**overrides: object) -> NewPatient:
    fields: dict[str, object] = {
        "first_name": "Ada",
        "last_name": "Smith",
        "mrn": "MRN-0001",
        "dob": date(1990, 1, 31),
        "gender": "female",
        "phone": "555-0100",
    }
    fields.update(overrides)
    return NewPatient(**fields)  # type: ignore[arg-type]


@pytest.fixture
def repo(db_session: AsyncSession, field_cipher: FieldCipher) -> PatientRepository:
    return PatientRepository(db_session, field_cipher)


async def test_create_then_get_round_trips_and_derives_search_fields(
    repo: PatientRepository, field_cipher: FieldCipher
) -> None:
    created = await repo.create(new_patient())

    loaded = await repo.get(created.id)

    assert loaded is not None
    assert (loaded.first_name, loaded.last_name, loaded.dob) == ("Ada", "Smith", date(1990, 1, 31))
    assert loaded.birth_year == 1990
    assert loaded.last_name_fp == field_cipher.fingerprint("last_name", "Smith")
    assert loaded.dob_fp == field_cipher.fingerprint("dob", "1990-01-31")


async def test_search_matches_last_name_prefixes_ignoring_case_and_spacing(
    repo: PatientRepository,
) -> None:
    smith = await repo.create(new_patient())
    smithers = await repo.create(new_patient(last_name="Smithers", mrn="MRN-0002"))
    await repo.create(new_patient(last_name="Jones", mrn="MRN-0003"))

    assert {p.id for p in await repo.search(last_name="  sMi ")} == {smith.id, smithers.id}
    assert [p.id for p in await repo.search(last_name="smithe")] == [smithers.id]
    assert await repo.search(last_name="mit") == []


async def test_names_shorter_than_the_prefix_minimum_match_exactly(
    repo: PatientRepository,
) -> None:
    li = await repo.create(new_patient(last_name="Li"))
    await repo.create(new_patient(last_name="Lim", mrn="MRN-0002"))

    assert [p.id for p in await repo.search(last_name="li")] == [li.id]


async def test_first_name_prefix_narrows_a_last_name_search(repo: PatientRepository) -> None:
    adeline = await repo.create(new_patient(first_name="Adeline"))
    await repo.create(new_patient(first_name="Adam", mrn="MRN-0002"))

    assert [p.id for p in await repo.search(last_name="smi", first_name="ade")] == [adeline.id]


async def test_search_by_dob_alone_and_combined_with_last_name(repo: PatientRepository) -> None:
    ada = await repo.create(new_patient())
    bob = await repo.create(new_patient(first_name="Bob", last_name="Jones", mrn="MRN-0002"))
    await repo.create(new_patient(dob=date(1991, 1, 31), mrn="MRN-0003"))

    assert {p.id for p in await repo.search(dob=date(1990, 1, 31))} == {ada.id, bob.id}
    assert [p.id for p in await repo.search(last_name="Jones", dob=date(1990, 1, 31))] == [bob.id]


async def test_search_orders_by_most_recent_visit(repo: PatientRepository) -> None:
    now = datetime.now(UTC)
    older = await repo.create(new_patient(mrn="MRN-0001"))
    newer = await repo.create(new_patient(mrn="MRN-0002"))
    never = await repo.create(new_patient(mrn="MRN-0003"))
    await repo.update(older.id, last_visit_at=now - timedelta(days=30))
    await repo.update(newer.id, last_visit_at=now)

    assert [p.id for p in await repo.search(last_name="Smith")] == [newer.id, older.id, never.id]


async def test_archived_patients_are_hidden_from_search_unless_requested(
    repo: PatientRepository,
) -> None:
    patient = await repo.create(new_patient())
    await repo.update(patient.id, archived_at=datetime.now(UTC), archive_reason="duplicate")

    assert await repo.search(last_name="Smith") == []
    assert [p.id for p in await repo.search(last_name="Smith", include_archived=True)] == [
        patient.id
    ]
    assert await repo.get(patient.id) is not None


async def test_updating_identifiers_keeps_search_in_sync(repo: PatientRepository) -> None:
    patient = await repo.create(new_patient())

    updated = await repo.update(patient.id, last_name="Jones", dob=date(1985, 6, 1))

    assert updated.birth_year == 1985
    assert await repo.search(last_name="Smith") == []
    assert await repo.search(last_name="smi") == []
    assert [p.id for p in await repo.search(last_name="Jones", dob=date(1985, 6, 1))] == [
        patient.id
    ]


async def test_duplicate_mrn_is_rejected_regardless_of_case_or_spacing(
    repo: PatientRepository,
) -> None:
    await repo.create(new_patient(mrn="MRN-0001"))

    with pytest.raises(DuplicateMrnError):
        await repo.create(new_patient(first_name="Other", mrn=" mrn-0001 "))

    assert len(await repo.search(last_name="Smith")) == 1


async def test_search_is_capped(repo: PatientRepository) -> None:
    for i in range(3):
        await repo.create(new_patient(mrn=f"MRN-{i}"))

    assert len(await repo.search(last_name="Smith", limit=2)) == 2


async def test_other_database_errors_are_not_mistaken_for_duplicate_mrns(
    repo: PatientRepository,
) -> None:
    patient = await repo.create(new_patient())

    with pytest.raises(IntegrityError):
        await repo.update(patient.id, status="asleep")
