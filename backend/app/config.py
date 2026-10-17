from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    env: Literal["development", "test", "production"] = "development"
    demo_mode: bool = False
    database_url: str
    keys_dir: Path = REPO_ROOT / ".keys"


def validate_settings(settings: Settings) -> None:
    """Refuse configurations that would expose the demo persona picker somewhere real."""
    if settings.demo_mode and (
        settings.env == "production" or "env" not in settings.model_fields_set
    ):
        raise RuntimeError("DEMO_MODE=true needs ENV set explicitly to development or test")


@lru_cache
def get_settings() -> Settings:
    return Settings()
