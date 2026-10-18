"""Time the patient endpoints against a running API (server-side latency incl. decryption).

Run from backend/ with the API up:  uv run python -m scripts.time_endpoints [--n 200]
"""

import argparse
import asyncio
import statistics
import time
from collections.abc import Awaitable, Callable

import httpx2

# Spec targets (p95, ms) at 10k patients.
TARGETS = {"list": 200, "search": 200, "counts": 150, "detail": 150}


async def _time(n: int, call: Callable[[], Awaitable[httpx2.Response]]) -> list[float]:
    samples = []
    for _ in range(n):
        start = time.perf_counter()
        response = await call()
        samples.append((time.perf_counter() - start) * 1000)
        response.raise_for_status()
    return samples


def _report(name: str, kind: str, samples: list[float]) -> None:
    p50 = statistics.median(samples)
    p95 = statistics.quantiles(samples, n=20)[18]
    target = TARGETS[kind]
    verdict = "ok" if p95 < target else "SLOW"
    print(f"{name:<30} p50 {p50:6.1f}ms  p95 {p95:6.1f}ms  target <{target}ms  {verdict}")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--n", type=int, default=200)
    args = parser.parse_args()

    async with httpx2.AsyncClient(base_url=f"{args.base_url}/api/v1", timeout=30) as client:
        personas = (await client.get("/personas")).json()
        chen = next(p for p in personas if p["name"] == "Dr. Wei Chen")
        client.headers["X-Persona"] = chen["id"]
        first = (await client.get("/patients", params={"scope": "all"})).json()["items"][0]
        prefix = first["last_name"][:3]

        cases: list[tuple[str, str, Callable[[], Awaitable[httpx2.Response]]]] = [
            ("list: all", "list", lambda: client.get("/patients", params={"scope": "all"})),
            ("list: my patients", "list", lambda: client.get("/patients", params={"scope": "my"})),
            (
                "list: by age",
                "list",
                lambda: client.get("/patients", params={"scope": "all", "sort": "age"}),
            ),
            (
                "list: today's visits",
                "list",
                lambda: client.get("/patients", params={"scope": "my", "filter": "today_visits"}),
            ),
            (
                "search: last-name prefix",
                "search",
                lambda: client.post(
                    "/patients/search", params={"scope": "all"}, json={"last_name": prefix}
                ),
            ),
            (
                "search: mrn",
                "search",
                lambda: client.post(
                    "/patients/search", params={"scope": "all"}, json={"mrn": first["mrn"]}
                ),
            ),
            (
                "filter counts: all",
                "counts",
                lambda: client.get("/patients/filter-counts", params={"scope": "all"}),
            ),
            (
                "filter counts: my",
                "counts",
                lambda: client.get("/patients/filter-counts", params={"scope": "my"}),
            ),
            ("detail", "detail", lambda: client.get(f"/patients/{first['id']}")),
        ]
        for name, kind, call in cases:
            await call()  # warm up
            _report(name, kind, await _time(args.n, call))


if __name__ == "__main__":
    asyncio.run(main())
