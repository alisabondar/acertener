from dataclasses import dataclass

import pytest

from app.ai import nlp


@dataclass
class _Hit:
    start: int
    end: int
    score: float
    entity_type: str = "PERSON"


def test_skips_weak_hits_redaction_tokens_and_medical_eponyms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = "Crohn's disease; [PATIENT]; maybe Pat; David Martinez"
    hits = [
        _Hit(0, 7, 0.9),  # "Crohn's": a condition, not a person
        _Hit(17, 26, 0.9),  # "[PATIENT]": already redacted
        _Hit(34, 37, 0.3),  # "Pat": too unsure to act on
        _Hit(39, 53, 0.85),  # "David Martinez"
    ]

    class FakeAnalyzer:
        def analyze(self, **_: object) -> list[_Hit]:
            return hits

    monkeypatch.setattr(nlp, "_analyzer", FakeAnalyzer)

    assert nlp.find_entities(text, ("PERSON",)) == [(39, 53, "PERSON")]
