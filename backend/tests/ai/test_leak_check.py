import pytest

from app.ai.identifiers import PatientIdentifiers
from app.ai.leak_check import leak_check


@pytest.mark.parametrize(
    ("text", "detector"),
    [
        ("Patient O'Neil is stable.", "patient_name"),
        ("rose oneil", "patient_name"),
        ("ref MRN-104412", "mrn"),
        ("chart 104412", "mrn"),
        ("id 0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d", "patient_id"),
        ("born 03/04/1956", "dob"),
        ("born 1956-03-04", "dob"),
        ("born March 4, 1956", "dob"),
        ("born 4 Mar 1956", "dob"),
        ("call 5558675309", "phone"),
        ("call 555.867.5309", "phone"),
        ("ROSE.ONEIL@EXAMPLE.ORG", "email"),
        ("742 evergreen terrace", "address"),
        ("zip 62704", "postal_code"),
        ("other id 123e4567-e89b-42d3-a456-426614174000", "uuid"),
        ("ssn 123-45-6789", "ssn"),
        ("see http://example.com", "url"),
        ("from 192.168.1.20", "ip_address"),
        ("someone@else.org", "email_pattern"),
        ("on 12/25/2025", "absolute_date"),
        ("Seen with Dr. Chen.", "staff_name"),
        ("Her son David Martinez drove her.", "person_name"),
    ],
)
def test_catches_identifiers_and_names_which_detector(
    ids: PatientIdentifiers, text: str, detector: str
) -> None:
    result = leak_check(text, ids)

    assert not result.ok
    assert detector in result.detectors


def test_the_word_mrn_alone_is_not_an_identifier(ids: PatientIdentifiers) -> None:
    assert leak_check("[PATIENT] identity and MRN verified at check-in.", ids).ok


def test_passes_a_clean_scrubbed_payload(ids: PatientIdentifiers) -> None:
    text = (
        '{"age": "70", "sex": "female", "notes": [{"day_offset": -7, "text": '
        '"[PATIENT] reports a cough since [DATE -10d]. Seen with [CLINICIAN]. BP 142/88."}]}'
    )

    assert leak_check(text, ids).ok


def test_never_reports_the_values_it_found(ids: PatientIdentifiers) -> None:
    result = leak_check("MRN-104412 Rose O'Neil 555-867-5309", ids)

    assert "104412" not in repr(result)
    assert "Rose" not in repr(result)


def test_a_drug_name_can_read_as_a_person_on_its_own(ids: PatientIdentifiers) -> None:
    """Why the next test exists: the name detector flags a bare drug name after a label."""
    assert "person_name" in leak_check("Allergies: Lisinopril (severe).", ids).detectors


def test_the_charts_own_clinical_terms_are_not_mistaken_for_names(ids: PatientIdentifiers) -> None:
    terms = frozenset({"Lisinopril", "Sulfa drugs"})

    assert leak_check("Allergies: Lisinopril (severe), Sulfa (mild).", ids, terms).ok


def test_a_clinical_term_never_hides_this_patients_name(ids: PatientIdentifiers) -> None:
    result = leak_check("Allergies: Rose (severe).", ids, frozenset({"Rose"}))

    assert "patient_name" in result.detectors
