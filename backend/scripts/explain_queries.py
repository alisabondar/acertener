"""EXPLAIN ANALYZE the exact SQL the patient endpoints run, against the dev database.

Run from backend/ after seeding:  uv run python -m scripts.explain_queries
"""

import asyncio
import re
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncConnection, async_sessionmaker

from app.config import get_settings
from app.crypto import FernetFieldCipher, load_or_create_keys
from app.db import create_engine
from app.db.models import AuditLog, Patient, User
from app.db.types import set_field_cipher
from app.patients.queries import (
    ListParams,
    build_counts_statement,
    build_list_statements,
    practice_today,
)
from app.schemas.patients import Order, QuickFilter, Scope, SearchTerms, Sort
from app.visits.queries import build_todays_visits_statement

AnySelect = Select[*tuple[Any, ...]]
LARGE_TABLES = ("patients", "visits", "patient_name_prefixes", "care_team_members", "audit_log")


DEFAULT_PARAMS = ListParams(
    scope=Scope.ALL,
    filter=None,
    status=None,
    include_archived=False,
    sort=Sort.LAST_VISIT,
    order=Order.DESC,
    page=1,
    page_size=20,
)


def _params(**overrides: Any) -> ListParams:
    return replace(DEFAULT_PARAMS, **overrides)


async def _explain(conn: AsyncConnection, name: str, statement: AnySelect) -> None:
    compiled = statement.compile(dialect=conn.dialect)
    params = tuple(compiled.params[key] for key in compiled.positiontup or ())
    result = await conn.exec_driver_sql(f"EXPLAIN (ANALYZE, BUFFERS) {compiled}", params)
    plan = [row[0] for row in result]
    timing = next((line for line in plan if line.startswith("Execution Time")), "?")
    seq_scans = sorted(
        {t for line in plan for t in LARGE_TABLES if re.search(rf"Seq Scan on {t}\b", line)}
    )
    flag = f"  ⚠ seq scan: {', '.join(seq_scans)}" if seq_scans else ""
    print(f"{name:<34} {timing}{flag}")


async def main() -> None:
    settings = get_settings()
    keys = load_or_create_keys(settings.keys_dir)
    cipher = FernetFieldCipher(keys.field_keys, keys.fingerprint_key)
    set_field_cipher(cipher)
    tz = ZoneInfo(settings.practice_timezone)
    today = practice_today(datetime.now(UTC), tz)
    engine = create_engine(settings.database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            conn = await session.connection()
            await conn.exec_driver_sql("ANALYZE")  # fresh planner statistics after seeding
            chen = await session.scalar(select(User).where(User.email == "chen@demo.clinic"))
            sample = await session.scalar(select(Patient).limit(1))
            if chen is None or sample is None:
                raise SystemExit("Seed the database first: uv run python -m scripts.seed")

            def lists(**kw: object) -> AnySelect:
                return build_list_statements(session, cipher, chen, _params(**kw), today, tz).page

            def search(terms: SearchTerms) -> AnySelect:
                built = build_list_statements(session, cipher, chen, _params(), today, tz, terms)
                return built.page

            cases: dict[str, AnySelect] = {
                "list: all, last visit": lists(),
                "list: my patients": lists(scope=Scope.MY),
                "list: all, by age": lists(sort=Sort.AGE, order=Order.ASC),
                "list: today's visits": lists(filter=QuickFilter.TODAY_VISITS),
                "list: all, page 50": lists(page=50),
                "list total: all": build_list_statements(
                    session, cipher, chen, _params(), today, tz
                ).total,
                "search: last-name prefix": search(SearchTerms(last_name=sample.last_name[:3])),
                "search: prefix + first name": search(
                    SearchTerms(last_name=sample.last_name[:3], first_name=sample.first_name[:3])
                ),
                "search: dob": search(SearchTerms(dob=sample.dob)),
                "search: mrn": search(SearchTerms(mrn=sample.mrn)),
                "filter counts: all": build_counts_statement(chen, Scope.ALL, today, tz),
                "filter counts: my": build_counts_statement(chen, Scope.MY, today, tz),
                "today's visits: my": build_todays_visits_statement(chen, Scope.MY, today, tz),
                "today's visits: all": build_todays_visits_statement(chen, Scope.ALL, today, tz),
                "detail": select(Patient).where(Patient.id == sample.id),
                "access log": select(AuditLog, User)
                .join(User, AuditLog.actor_id == User.id)
                .where(AuditLog.patient_id == sample.id)
                .order_by(AuditLog.id.desc())
                .limit(50),
            }
            for name, statement in cases.items():
                await _explain(conn, name, statement)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
