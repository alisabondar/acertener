"""How a patient's problems are listed: why they're here today, then chronic disease, then the rest.

This is the order a clinician scans a problem list in before a visit.
"""

from collections.abc import Iterable

# ICD-10 categories of long-term conditions seen often in primary care (by code prefix).
CHRONIC_ICD10_PREFIXES = (
    "E08", "E09", "E10", "E11", "E13",  # diabetes
    "E03", "E05",  # thyroid disease
    "E66",  # obesity
    "E78",  # lipid disorders
    "F17",  # nicotine dependence
    "F31", "F32", "F33", "F41",  # bipolar disorder, depression, anxiety
    "G20", "G40", "G43",  # Parkinson's, epilepsy, migraine
    "I10", "I11", "I12", "I13", "I15",  # hypertension
    "I25", "I48", "I50",  # coronary disease, atrial fibrillation, heart failure
    "J44", "J45",  # COPD, asthma
    "K21", "K50", "K51",  # GERD, inflammatory bowel disease
    "M05", "M06", "M15", "M16", "M17", "M19", "M81",  # arthritis, osteoporosis
    "N18",  # chronic kidney disease
)  # fmt: skip


def is_chronic(icd10_code: str) -> bool:
    return icd10_code.upper().startswith(CHRONIC_ICD10_PREFIXES)


def order_problems(todays_reason: str | None, conditions: Iterable[tuple[str, str]]) -> list[str]:
    """Today's visit reason (if any), then chronic conditions, then the rest, each in order."""
    listed = list(conditions)
    chronic = [name for code, name in listed if is_chronic(code)]
    other = [name for code, name in listed if not is_chronic(code)]
    return ([f"Today: {todays_reason}"] if todays_reason else []) + chronic + other
