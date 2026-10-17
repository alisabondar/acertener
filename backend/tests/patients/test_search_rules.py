import pytest

from app.patients.repository import PatientRepository, name_prefixes
from app.schemas.patients import SearchTerms


@pytest.mark.anyio
async def test_search_needs_last_name_or_dob() -> None:
    repo = PatientRepository(session=None, cipher=None)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="last_name, dob, or mrn"):
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


@pytest.mark.parametrize("terms", [{"mrn": "MRN-1"}, {"last_name": "smi"}, {"dob": "1970-01-01"}])
def test_any_anchor_field_is_enough_to_search(terms: dict[str, str]) -> None:
    SearchTerms.model_validate(terms)


def test_first_name_alone_is_not_enough() -> None:
    with pytest.raises(ValueError, match="last_name, dob, or mrn"):
        SearchTerms.model_validate({"first_name": "Ada"})
