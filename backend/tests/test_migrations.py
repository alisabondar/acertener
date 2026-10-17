import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import Base
from tests.helpers import alembic_config


@pytest.mark.db
def test_migrations_upgrade_downgrade_and_upgrade_again(settings: Settings) -> None:
    config = alembic_config(settings.database_url)

    command.upgrade(config, "head")
    command.downgrade(config, "base")
    command.upgrade(config, "head")


def test_migrations_accept_a_url_encoded_password() -> None:
    config = alembic_config("postgresql+asyncpg://app:p%40ss@localhost/app")

    command.upgrade(config, "head", sql=True)


@pytest.mark.db
@pytest.mark.anyio
async def test_models_match_the_migrated_schema(db_session: AsyncSession) -> None:
    conn = await db_session.connection()

    diff = await conn.run_sync(
        lambda sync_conn: compare_metadata(MigrationContext.configure(sync_conn), Base.metadata)
    )

    assert diff == []
