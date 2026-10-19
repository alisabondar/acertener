"""An independent, fail-closed scan of exactly what would be sent to (or came back from) the AI.

It deliberately shares no code with the scrubber: a bug there must not also hide here. Any hit
blocks the request. Results name detectors only, never the values they matched.
"""

import re
from dataclasses import dataclass
from datetime import date

from app.ai.identifiers import PatientIdentifiers
from app.ai.nlp import find_entities


@dataclass(frozen=True)
class LeakResult:
    detectors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.detectors


_GENERIC: dict[str, re.Pattern[str]] = {
    "uuid": re.compile(
        r"\b[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}\b", re.I
    ),
    "ssn": re.compile(r"\b\d{3}[-\s]\d{2}[-\s]\d{4}\b"),
    "url": re.compile(r"https?://|\bwww\.", re.I),
    "ip_address": re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"),
    "email_pattern": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "phone_pattern": re.compile(r"\(?\b\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b"),
    # The number is the identifier; the word alone ("MRN verified") is not.
    "mrn_pattern": re.compile(r"\bMRN[\s#:-]*\d+", re.I),
    # Any absolute date outside a [DATE …] token; offsets are the only dates allowed out.
    "absolute_date": re.compile(
        r"\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b|"
        r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b",
        re.I,
    ),
}


def _normalize(text: str) -> str:
    """Lower case, apostrophes (straight or curly) and dots removed, whitespace collapsed."""
    text = re.sub("['\u2019`.]", "", text.lower())
    return re.sub(r"\s+", " ", text)


def _digits_joined(text: str) -> str:
    """Digits with separators between them removed, so 555.867-5309 reads as 5558675309."""
    return re.sub(r"(?<=\d)[\s().-]+(?=\d)", "", text)


def _contains_word(haystack: str, needle: str) -> bool:
    return (
        bool(needle) and re.search(rf"(?<![\w-]){re.escape(needle)}(?![\w-])", haystack) is not None
    )


def _dob_forms(dob: date) -> set[str]:
    m, d, y = dob.month, dob.day, dob.year
    month_names = [dob.strftime("%B").lower(), dob.strftime("%b").lower()]
    forms = {
        f"{y:04d}-{m:02d}-{d:02d}",
        f"{m:02d}/{d:02d}/{y:04d}",
        f"{m}/{d}/{y}",
        f"{m:02d}/{d:02d}/{y % 100:02d}",
        f"{m}/{d}/{y % 100:02d}",
        f"{m:02d}-{d:02d}-{y:04d}",
        f"{y:04d}{m:02d}{d:02d}",
    }
    for name in month_names:
        forms |= {f"{name} {d}, {y}", f"{name} {d} {y}", f"{d} {name} {y}"}
    return forms


def _identifier_hits(text: str, ids: PatientIdentifiers) -> set[str]:
    normal = _normalize(text)
    digits = _digits_joined(text)
    hits: set[str] = set()

    name_tokens = {_normalize(ids.first_name), _normalize(ids.last_name)}
    if any(len(t) >= 2 and _contains_word(normal, t) for t in name_tokens):
        hits.add("patient_name")
    mrn_digits = re.sub(r"\D", "", ids.mrn)
    if _contains_word(normal, _normalize(ids.mrn)) or (
        mrn_digits and _contains_word(digits, mrn_digits)
    ):
        hits.add("mrn")
    pid = str(ids.patient_id).lower()
    if pid in text.lower() or pid.replace("-", "") in text.lower():
        hits.add("patient_id")
    if any(form in normal for form in _dob_forms(ids.dob)):
        hits.add("dob")
    if ids.phone:
        phone = re.sub(r"\D", "", ids.phone)
        if len(phone) >= 7 and (phone in digits or phone[-7:] in digits):
            hits.add("phone")
    if ids.email and ids.email.lower() in text.lower():
        hits.add("email")
    for part in (ids.address_line1, ids.address_line2, ids.city):
        if part and len(part) >= 4 and _contains_word(normal, _normalize(part)):
            hits.add("address")
    if ids.postal_code and _contains_word(digits, ids.postal_code):
        hits.add("postal_code")
    for staff in ids.staff_names:
        tokens = [_normalize(t) for t in staff.replace("Dr.", "").split()]
        if any(len(t) >= 3 and _contains_word(normal, t) for t in tokens):
            hits.add("staff_name")
    return hits


def leak_check(
    text: str, ids: PatientIdentifiers, clinical_terms: frozenset[str] = frozenset()
) -> LeakResult:
    """Every detector that fires on `text`; empty means nothing identifying was found.

    `clinical_terms` are the chart's own allergy and condition names (already scrubbed). The name
    detector can read a bare drug like "Lisinopril" as a person, so a detected name made only of
    those words is skipped. The exact checks for this patient's identifiers still run first.
    """
    hits = _identifier_hits(text, ids)
    hits |= {name for name, pattern in _GENERIC.items() if pattern.search(text)}
    known = {word.casefold() for term in clinical_terms for word in term.split()}
    for start, end, kind in find_entities(text, ("PERSON", "LOCATION")):
        if known and all(word.casefold() in known for word in text[start:end].split()):
            continue
        hits.add("person_name" if kind == "PERSON" else "location")
    return LeakResult(tuple(sorted(hits)))
