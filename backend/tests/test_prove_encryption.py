import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import FieldCipher
from app.db.models import Patient
from scripts.prove_encryption import database_as_text, pg_dump_command, run_proof


@pytest.mark.db
@pytest.mark.anyio
@pytest.mark.privacy
async def test_proof_shows_plaintext_in_the_app_and_only_ciphertext_in_the_database(
    db_session: AsyncSession, field_cipher: FieldCipher
) -> None:
    async def dump() -> str:
        return await database_as_text(db_session)

    result = await run_proof(db_session, field_cipher, dump)

    assert result.app_view["last_name"] == result.canary_name
    assert all(value.startswith("v1:") for value in result.raw_row.values())
    assert result.dump_matches == 0
    assert result.wrong_key_refused
    assert await db_session.get(Patient, result.patient_id) is None


def test_pg_dump_targets_the_database_the_canary_was_written_to() -> None:
    command, env = pg_dump_command("postgresql+asyncpg://clinic_user:pw@db:5433/clinic")

    assert command == ["pg_dump", "-h", "db", "-p", "5433", "-U", "clinic_user", "clinic"]
    # The password travels in the environment, never in the process list.
    assert "pw" not in " ".join(command)
    assert env["PGPASSWORD"] == "pw"
