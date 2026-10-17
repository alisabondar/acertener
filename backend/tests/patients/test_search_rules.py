import pytest

from app.patients.repository import PatientRepository, name_prefixes


@pytest.mark.anyio
async def test_search_needs_last_name_or_dob() -> None:
    repo = PatientRepository(session=None, cipher=None)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="last_name or dob"):
        await repo.search()


@pytest.mark.anyio
async def test_unknown_or_derived_fields_cannot_be_updated_directly() -> None:
    repo = PatientRepository(session=None, cipher=None)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="last_name_fp"):
        await repo.update(None, last_name_fp=b"forged")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Smith", {"smi", "smit", "smith"}),
        ("  LI ", {"li"}),
        ("Van  Der", {"van", "van ", "van d", "van de", "van der"}),
    ],
)
def test_name_prefixes_are_normalized_and_include_the_whole_name(
    name: str, expected: set[str]
) -> None:
    assert name_prefixes(name) == expected
