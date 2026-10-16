from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config import Settings

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_migrations_upgrade_downgrade_and_upgrade_again(settings: Settings) -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["database_url"] = settings.database_url
    config.attributes["configure_logging"] = False

    command.upgrade(config, "head")
    command.downgrade(config, "base")
    command.upgrade(config, "head")


def test_migrations_accept_a_url_encoded_password() -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["database_url"] = "postgresql+asyncpg://app:p%40ss@localhost/app"
    config.attributes["configure_logging"] = False

    command.upgrade(config, "head", sql=True)
