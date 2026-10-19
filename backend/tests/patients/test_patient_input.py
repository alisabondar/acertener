import pytest
from pydantic import ValidationError

from app.schemas.patients import PatientChanges, PatientFields


@pytest.mark.parametrize("field", ["first_name", "last_name", "mrn", "dob"])
def test_required_fields_cannot_be_cleared(field: str) -> None:
    with pytest.raises(ValidationError, match="can't be cleared"):
        PatientChanges.model_validate({field: None})


def test_optional_fields_can_be_cleared() -> None:
    changes = PatientChanges.model_validate({"city": None, "phone": None})

    assert changes.model_dump(exclude_unset=True) == {"city": None, "phone": None}


VALID = {"first_name": "Ada", "last_name": "Smith", "mrn": "MRN-100000", "dob": "1984-02-29"}


@pytest.mark.parametrize(
    "name",
    [
        "O'Neil",
        "Mary-Jane",
        "José",
        "Nguyễn",
        "St. John",
        "D'Angelo-Smith",
        "Smith Jr.",
        "Ng",
        "Li",
    ],
)
def test_real_names_are_accepted(name: str) -> None:
    patient = PatientFields.model_validate({**VALID, "last_name": name, "first_name": name})

    assert patient.last_name == name


@pytest.mark.parametrize(
    "name", ["x1!!", "123", "Smith3", "--", "O''Neil", "Ann  Lee!", "<script>", "a@b", "."]
)
def test_names_must_look_like_names(name: str) -> None:
    with pytest.raises(ValidationError, match="letters"):
        PatientFields.model_validate({**VALID, "last_name": name})


def test_inner_spaces_in_names_are_collapsed() -> None:
    assert PatientFields.model_validate({**VALID, "first_name": "Mary   Ann"}).first_name == (
        "Mary Ann"
    )


@pytest.mark.parametrize(
    ("field", "good", "bad"),
    [
        ("mrn", "MRN-100000", "MRN 1!"),
        ("mrn", "A12345", "MRN-"),
        ("phone", "555-867-5309", "555-0100"),
        ("phone", "(555) 867 5309", "call me"),
        ("phone", "+1 555 867 5309", "+44 20 7946 0958 1234"),
        ("email", "ada.smith@example.org", "ada@"),
        ("email", "a+tag@mail.example.co", "not an email"),
        ("state", "NY", "New York"),
        ("state", "dc", "ZZ"),
        ("postal_code", "02139", "2139"),
        ("postal_code", "02139-4307", "ABCDE"),
        ("city", "Winston-Salem", "123"),
        ("address_line1", "742 Evergreen Terrace", "!!!"),
    ],
)
def test_contact_details_are_checked(field: str, good: str, bad: str) -> None:
    assert PatientFields.model_validate({**VALID, field: good})
    with pytest.raises(ValidationError):
        PatientFields.model_validate({**VALID, field: bad})


def test_phone_and_state_are_stored_in_one_format() -> None:
    patient = PatientFields.model_validate({**VALID, "phone": "(555) 867 5309", "state": "ny"})

    assert (patient.phone, patient.state) == ("555-867-5309", "NY")


def test_edits_follow_the_same_rules() -> None:
    with pytest.raises(ValidationError, match="letters"):
        PatientChanges.model_validate({"last_name": "x1!!"})
