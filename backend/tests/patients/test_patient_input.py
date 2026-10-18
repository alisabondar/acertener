import pytest
from pydantic import ValidationError

from app.schemas.patients import PatientChanges


@pytest.mark.parametrize("field", ["first_name", "last_name", "mrn", "dob"])
def test_required_fields_cannot_be_cleared(field: str) -> None:
    with pytest.raises(ValidationError, match="can't be cleared"):
        PatientChanges.model_validate({field: None})


def test_optional_fields_can_be_cleared() -> None:
    changes = PatientChanges.model_validate({"city": None, "phone": None})

    assert changes.model_dump(exclude_unset=True) == {"city": None, "phone": None}
