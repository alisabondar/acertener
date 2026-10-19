"""A clinic's working day against the API: providers, nurses, and front desk at once.

Run from backend/ with the API up (demo mode) and the database seeded:

    uv run locust -f loadtest/locustfile.py --host http://localhost:8000 \\
        --headless -u 50 -r 10 -t 3m --csv loadtest/results/run

Each simulated user picks a persona and browses as that role would. Request names group the
results by endpoint (list, search, counts, detail, ...), matching the latency targets.
"""

import random
from typing import ClassVar

from locust import HttpUser, between, task

API = "/api/v1"
PREFIXES = ["sm", "joh", "wil", "bro", "jon", "gar", "mil", "dav", "rod", "mar", "her", "lop"]
# Role -> persona IDs, fetched once by whichever simulated user starts first.
personas: dict[str, list[str]] = {}


class Staff(HttpUser):
    abstract = True
    role: ClassVar[str]
    wait_time = between(1, 4)
    patient_ids: list[str]

    def on_start(self) -> None:
        if not personas:
            for persona in self.client.get(f"{API}/personas", name="personas").json():
                personas.setdefault(persona["role"], []).append(persona["id"])
        self.client.headers["X-Persona"] = random.choice(personas[self.role])
        page = self.client.get(f"{API}/patients", params={"scope": "all"}, name="list").json()
        self.patient_ids = [p["id"] for p in page["items"]]

    def list_patients(self, **params: str) -> None:
        response = self.client.get(
            f"{API}/patients", params={"scope": "all", **params}, name="list"
        )
        if response.ok:
            self.patient_ids = [p["id"] for p in response.json()["items"]] or self.patient_ids
        self.client.get(f"{API}/patients/filter-counts", params={"scope": "all"}, name="counts")

    def search(self) -> None:
        body = {"last_name": random.choice(PREFIXES)}
        self.client.post(
            f"{API}/patients/search", params={"scope": "all"}, json=body, name="search"
        )

    def open_chart(self, *parts: str) -> None:
        patient = random.choice(self.patient_ids)
        self.client.get(f"{API}/patients/{patient}", name="detail")
        for part in parts:
            self.client.get(f"{API}/patients/{patient}/{part}", name=f"chart: {part}")


class Provider(Staff):
    role = "provider"
    weight = 4

    @task(3)
    def my_day(self) -> None:
        self.client.get(f"{API}/visits/today", params={"scope": "my"}, name="my day")

    @task(3)
    def browse(self) -> None:
        self.list_patients(scope="my", page=str(random.randint(1, 5)))

    @task(4)
    def find_patient(self) -> None:
        self.search()

    @task(6)
    def chart(self) -> None:
        self.open_chart("notes", "vitals", "conditions", "allergies", "summary")


class Nurse(Staff):
    role = "nurse"
    weight = 3

    @task(2)
    def browse(self) -> None:
        self.list_patients(filter="today_visits")

    @task(2)
    def find_patient(self) -> None:
        self.search()

    @task(5)
    def chart(self) -> None:
        self.open_chart("vitals", "allergies", "conditions")


class FrontDesk(Staff):
    role = "front_desk"
    weight = 3

    @task(3)
    def browse(self) -> None:
        self.list_patients(sort=random.choice(["last_visit", "age"]))

    @task(5)
    def find_patient(self) -> None:
        self.search()

    @task(2)
    def contact(self) -> None:
        self.open_chart()
