import pytest

from app.ai.identifiers import PatientIdentifiers
from app.ai.scrub import scrub
from tests.ai.conftest import TODAY


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # The patient, in every form a clinician might write.
        ("Rose O'Neil came in today.", "[PATIENT] came in today."),
        ("Mrs. O'Neil's daughter called.", "[PATIENT]'s daughter called."),
        ("Ms. ONEIL reports pain.", "[PATIENT] reports pain."),
        ("Pt Rose says the cough is better.", "Pt [PATIENT] says the cough is better."),
        # Staff become [CLINICIAN], other people [PERSON].
        ("Seen with Dr. Chen and Sam Okafor, RN.", "Seen with [CLINICIAN] and [CLINICIAN], RN."),
        ("Her son David Martinez drove her.", "Her son [PERSON] drove her."),
        # Dates become offsets from today, in any common format.
        (
            "Last seen 3/4/56 and again 2026-10-12.",
            "Last seen [DATE -25796d] and again [DATE -7d].",
        ),
        ("Started on March 4, 2026.", "Started on [DATE -229d]."),
        ("Started on 4 March 2026.", "Started on [DATE -229d]."),
        # Contact details and identifiers are removed outright.
        ("Call back at (555) 867-5309.", "Call back at [REDACTED]."),
        ("Call five five five eight six seven five three zero nine.", "Call [REDACTED]."),
        (
            "Email rose.oneil@example.org or see https://portal.example.org/x",
            "Email [REDACTED] or see [REDACTED]",
        ),
        (
            "Lives at 742 Evergreen Terrace, Springfield 62704.",
            "Lives at [REDACTED], [REDACTED] [REDACTED].",
        ),
        (
            "SSN 123-45-6789, MRN-104412, from 10.0.0.12.",
            "SSN [REDACTED], [REDACTED], from [REDACTED].",
        ),
    ],
)
def test_scrubs_the_tricky_corpus(ids: PatientIdentifiers, text: str, expected: str) -> None:
    assert scrub(text, ids, TODAY) == expected


@pytest.mark.parametrize(
    "text",
    [
        "BP 142/88, HR 76, SpO2 98%. Continue lisinopril 10 mg daily.",
        "A1c 7.2%. Follow up in 3 months. Parkinson disease ruled out.",
        "Rose-colored rash on the left forearm.",
    ],
)
def test_leaves_clinical_content_alone(ids: PatientIdentifiers, text: str) -> None:
    assert scrub(text, ids, TODAY) == text


def test_an_impossible_date_is_hidden_rather_than_guessed(ids: PatientIdentifiers) -> None:
    assert scrub("Recheck 13/45/2026.", ids, TODAY) == "Recheck [DATE]."


def test_single_word_staff_names_are_removed_and_empty_ones_ignored(
    ids: PatientIdentifiers,
) -> None:
    staff = PatientIdentifiers(**{**vars(ids), "staff_names": ("Dr.", "Nightingale")})

    assert scrub("Discussed with Nightingale.", staff, TODAY) == "Discussed with [CLINICIAN]."
