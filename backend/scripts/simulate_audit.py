"""Fill the audit log with simulated history, to load-test against a realistic table size.

Adds chart views spread over the past year, by real staff on real patients. The rows carry no
change values (views record none), so nothing here needs encrypting. Development only.

Run from backend/ after seeding:  uv run python -m scripts.simulate_audit [--rows 1000000]
"""

import argparse
import asyncio
import time

from sqlalchemy import text

from app.config import get_settings
from app.db import create_engine
from scripts.seed import require_development

# Postgres generates the rows itself, so a million take seconds rather than a round trip each.
INSERT_VIEWS = text("""
    WITH staff AS (SELECT array_agg(id) AS ids FROM users WHERE role <> 'admin'),
         patients AS (SELECT array_agg(id) AS ids FROM patients)
    INSERT INTO audit_log
        (occurred_at, actor_id, via_demo_persona, action, entity, entity_id, patient_id, request_id)
    SELECT occurred_at, actor_id, false, 'view', 'patient', patient_id, patient_id, 'simulated'
    FROM (
        SELECT now() - random() * interval '365 days' AS occurred_at,
               staff.ids[1 + floor(random() * cardinality(staff.ids))::int] AS actor_id,
               patients.ids[1 + floor(random() * cardinality(patients.ids))::int] AS patient_id
        FROM generate_series(1, :rows), staff, patients
    ) generated
    -- Oldest first, so ids follow time like real entries do.
    ORDER BY occurred_at
""")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=1_000_000)
    args = parser.parse_args()

    settings = get_settings()
    require_development(settings.env)
    engine = create_engine(settings.database_url)
    started = time.monotonic()
    try:
        async with engine.begin() as conn:
            await conn.execute(INSERT_VIEWS, {"rows": args.rows})
            await conn.execute(text("ANALYZE audit_log"))
            total = (await conn.execute(text("SELECT count(*) FROM audit_log"))).scalar_one()
    finally:
        await engine.dispose()
    print(f"Added {args.rows:,} audit rows in {time.monotonic() - started:.1f}s ({total:,} total).")


if __name__ == "__main__":
    asyncio.run(main())
