"""Show that patient identifiers are readable in the app and unreadable in the database.

Run from backend/ with the dev database up:  uv run python -m scripts.prove_encryption
"""

import asyncio
import os
import secrets
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date

from cryptography.fernet import Fernet
from sqlalchemy import column, literal_column, select, table, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.crypto import DecryptionError, FernetFieldCipher, FieldCipher, load_or_create_keys
from app.db import create_engine
from app.db.types import set_field_cipher
from app.patients.repository import NewPatient, PatientRepository

SHOWN_COLUMNS = ("first_name", "last_name", "mrn", "dob")


@dataclass(frozen=True)
class ProofResult:
    patient_id: uuid.UUID
    canary_name: str
    app_view: dict[str, str]
    raw_row: dict[str, str]
    dump_matches: int
    wrong_key_refused: bool


async def database_as_text(session: AsyncSession) -> str:
    """Every row of every table rendered as text: what a database dump would contain."""
    tables = await session.scalars(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
        )
    )
    rows: list[str] = []
    for name in tables.all():
        rows.extend(
            await session.scalars(
                select(literal_column("t::text")).select_from(table(name).alias("t"))
            )
        )
    return "\n".join(rows)


async def run_proof(
    session: AsyncSession, cipher: FieldCipher, dump: Callable[[], Awaitable[str]]
) -> ProofResult:
    canary = f"Canary{secrets.token_hex(4)}"
    patient = await PatientRepository(session, cipher).create(
        NewPatient(
            first_name="Proof", last_name=canary, mrn=f"PROOF-{canary}", dob=date(1970, 1, 1)
        )
    )
    await session.commit()
    try:
        app_view = {name: str(getattr(patient, name)) for name in SHOWN_COLUMNS}
        raw = table("patients", column("id"), *(column(name) for name in SHOWN_COLUMNS))
        raw_row = dict(
            (
                await session.execute(
                    select(*(raw.c[name] for name in SHOWN_COLUMNS)).where(raw.c.id == patient.id)
                )
            )
            .one()
            ._mapping
        )
        wrong_cipher = FernetFieldCipher([Fernet.generate_key()], Fernet.generate_key())
        try:
            wrong_cipher.decrypt(raw_row["last_name"])
            wrong_key_refused = False
        except DecryptionError:
            wrong_key_refused = True
        return ProofResult(
            patient_id=patient.id,
            canary_name=canary,
            app_view=app_view,
            raw_row=raw_row,
            dump_matches=(await dump()).count(canary),
            wrong_key_refused=wrong_key_refused,
        )
    finally:
        await session.delete(patient)
        await session.commit()


def pg_dump_command(database_url: str) -> tuple[list[str], dict[str, str]]:
    """Dump exactly the database the app wrote to, using the host, user, and name from its URL.

    The password goes in PGPASSWORD rather than the arguments, which any local user can list.
    """
    url = make_url(database_url)
    command = [
        "pg_dump",
        "-h",
        str(url.host),
        "-p",
        str(url.port or 5432),
        "-U",
        str(url.username),
        str(url.database),
    ]
    return command, {**os.environ, "PGPASSWORD": str(url.password or "")}


async def _pg_dump(database_url: str) -> str:
    # Fixed argument list and no shell; `pg_dump` is resolved from PATH on purpose.
    command, env = pg_dump_command(database_url)
    process = await asyncio.create_subprocess_exec(
        *command, env=env, stdout=asyncio.subprocess.PIPE
    )
    stdout, _ = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(f"pg_dump failed with exit code {process.returncode}")
    return stdout.decode()


def _print_section(title: str, rows: dict[str, str]) -> None:
    print(f"\n{title}")
    for name, value in rows.items():
        print(f"  {name:<11} {value}")


async def main() -> None:
    settings = get_settings()
    keys = load_or_create_keys(settings.keys_dir)
    cipher = FernetFieldCipher(keys.field_keys, keys.fingerprint_key)
    set_field_cipher(cipher)
    engine = create_engine(settings.database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            result = await run_proof(session, cipher, lambda: _pg_dump(settings.database_url))
    finally:
        await engine.dispose()

    _print_section("1. What the app sees", result.app_view)
    _print_section("2. What the database stores", result.raw_row)
    print(f"\n3. pg_dump | grep {result.canary_name!r}\n  {result.dump_matches} matches")
    refused = "refused: value could not be decrypted" if result.wrong_key_refused else "DECRYPTED"
    print(f"\n4. Decrypt with a different key\n  {refused}")
    print("\nThe canary patient has been removed.")


if __name__ == "__main__":
    asyncio.run(main())
