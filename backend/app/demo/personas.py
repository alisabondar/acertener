from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    name: str
    email: str
    role: str
    credential: str | None


# The curated staff the "View as" picker offers, in display order.
PERSONAS = [
    Persona("Dr. Wei Chen", "chen@demo.clinic", "provider", "MD"),
    Persona("Jordan Rivera", "rivera@demo.clinic", "provider", "NP"),
    Persona("Sam Okafor", "okafor@demo.clinic", "nurse", "RN"),
    Persona("Taylor Brooks", "brooks@demo.clinic", "front_desk", None),
    Persona("Practice Admin", "admin@demo.clinic", "admin", None),
]
