"""Remove identifiers from clinical free text before it can go into an AI payload.

Order matters: contact details and identifiers first (so their digits aren't read as dates),
then dates, then known names, and last any other person a name detector finds.
"""

import re
from datetime import date

from app.ai.identifiers import PatientIdentifiers
from app.ai.nlp import find_entities

REDACTED = "[REDACTED]"

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
_URL = re.compile(r"\bhttps?://\S+|\bwww\.\S+", re.IGNORECASE)
_IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_MRN = re.compile(r"\bMRN[-\s]?\d+\b", re.IGNORECASE)
_PHONE = re.compile(r"(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\b\d{3})[\s.-]?\d{3}[\s.-]?\d{4}\b")
_DIGIT_WORDS = r"(?:zero|oh|one|two|three|four|five|six|seven|eight|nine)"
# Seven or more spelled-out digits in a row is a phone number written in words.
_PHONE_WORDS = re.compile(rf"\b{_DIGIT_WORDS}(?:[\s,-]+{_DIGIT_WORDS}){{6,}}\b", re.IGNORECASE)
_STREET = re.compile(
    r"\b\d{1,6}\s+(?:[A-Z][a-z]+\s+){1,3}"
    r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Terrace|Ter|Court|Ct|"
    r"Way|Place|Pl|Circle|Cir|Parkway|Pkwy)\b\.?"
)

_MONTHS = {
    m: i
    for i, names in enumerate(
        [
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        ],
        start=1,
    )
    for m in names
}
_MONTH = r"(?:" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")\.?"
_DATE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"), "ymd"),
    (re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b"), "mdy"),
    (re.compile(rf"\b({_MONTH})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b", re.I), "Mdy"),
    (re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH}),?\s+(\d{{4}})\b", re.I), "dMy"),
]


def _year(raw: str, today: date) -> int:
    year = int(raw)
    if year >= 100:
        return year
    # Two-digit years: the most recent past century that keeps the date out of the future.
    century = today.year // 100 * 100
    return century + year if century + year <= today.year else century - 100 + year


def _as_date(match: re.Match[str], kind: str, today: date) -> date | None:
    try:
        if kind == "ymd":
            return date(int(match[1]), int(match[2]), int(match[3]))
        if kind == "mdy":
            return date(_year(match[3], today), int(match[1]), int(match[2]))
        if kind == "Mdy":
            return date(int(match[3]), _MONTHS[match[1].lower().rstrip(".")], int(match[2]))
        return date(int(match[3]), _MONTHS[match[2].lower().rstrip(".")], int(match[1]))
    except ValueError:
        return None


def _dates_to_offsets(text: str, today: date) -> str:
    for pattern, kind in _DATE_PATTERNS:

        def offset(match: re.Match[str], kind: str = kind) -> str:
            day = _as_date(match, kind, today)
            return f"[DATE {(day - today).days}d]" if day else "[DATE]"

        text = pattern.sub(offset, text)
    return text


def _surname_pattern(surname: str) -> str:
    """Matches O'Neil, ONeil, and Oneil (straight or curly apostrophe, or none), any case."""
    letters = [re.escape(c) for c in surname if c.isalnum()]
    return "['\u2019]?".join(letters)


def _name_pattern(first: str, last: str) -> re.Pattern[str]:
    title = r"(?:(?:Mr|Mrs|Ms|Miss|Mx|Dr)\.?\s+)?"
    last_p = _surname_pattern(last)
    first_p = re.escape(first)
    # Not followed by a hyphen: "Rose-colored rash" is a colour, not the patient.
    return re.compile(
        rf"\b{title}(?:{first_p}\s+{last_p}|{last_p}|{first_p})\b(?![-\w])", re.IGNORECASE
    )


def _staff_pattern(full_name: str) -> re.Pattern[str] | None:
    parts = full_name.replace("Dr.", "").split()
    if not parts:
        return None
    last = parts[-1]
    first = parts[0] if len(parts) > 1 else None
    title = r"(?:Dr\.?\s+)?"
    options = [_surname_pattern(last)]
    if first:
        options.insert(0, rf"{re.escape(first)}\s+{_surname_pattern(last)}")
    return re.compile(rf"\b{title}(?:{'|'.join(options)})\b(?![-\w])", re.IGNORECASE)


def scrub(text: str, ids: PatientIdentifiers, today: date) -> str:
    for pattern in (_EMAIL, _URL, _IP, _SSN, _MRN, _PHONE, _PHONE_WORDS):
        text = pattern.sub(REDACTED, text)
    for known in (ids.address_line1, ids.address_line2, ids.city, ids.postal_code):
        if known:
            text = re.sub(rf"\b{re.escape(known)}\b", REDACTED, text, flags=re.IGNORECASE)
    text = _STREET.sub(REDACTED, text)
    text = _dates_to_offsets(text, today)

    text = _name_pattern(ids.first_name, ids.last_name).sub("[PATIENT]", text)
    for staff in ids.staff_names:
        if staff_pattern := _staff_pattern(staff):
            text = staff_pattern.sub("[CLINICIAN]", text)

    # Anyone else a name detector finds (family, other patients), replaced from the end so
    # earlier offsets stay valid.
    for start, end, _ in reversed(find_entities(text, ("PERSON",))):
        text = text[:start] + "[PERSON]" + text[end:]
    return text
