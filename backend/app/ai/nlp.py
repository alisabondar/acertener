"""Named-entity detection (people and places) with Presidio over spaCy's small English model."""

from functools import lru_cache

from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider

# Medical eponyms look like surnames to a name detector; they're conditions, not people.
EPONYMS = frozenset(
    {
        "addison",
        "alzheimer",
        "asperger",
        "bell",
        "crohn",
        "cushing",
        "down",
        "gehrig",
        "graves",
        "guillain",
        "barre",
        "hashimoto",
        "hodgkin",
        "huntington",
        "kawasaki",
        "parkinson",
        "raynaud",
        "sjogren",
        "tourette",
        "wilson",
    }
)
MIN_SCORE = 0.6


@lru_cache(maxsize=1)
def _analyzer() -> AnalyzerEngine:
    nlp_engine = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
        }
    ).create_engine()
    return AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])


def warm_up() -> None:
    """Load the language model now, so the first summary after a restart doesn't wait for it."""
    _analyzer()


def find_entities(text: str, kinds: tuple[str, ...]) -> list[tuple[int, int, str]]:
    """(start, end, kind) spans of people or places, skipping redaction tokens and eponyms."""
    spans = []
    for hit in _analyzer().analyze(text=text, entities=list(kinds), language="en"):
        found = text[hit.start : hit.end]
        if hit.score < MIN_SCORE or "[" in found or "]" in found:
            continue
        words = {w.strip("'\u2019s").lower() for w in found.split()}
        if words & EPONYMS:
            continue
        spans.append((hit.start, hit.end, hit.entity_type))
    return sorted(spans)
