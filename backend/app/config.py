from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    env: Literal["development", "test", "production"] = "development"
    database_url: str
    keys_dir: Path = REPO_ROOT / ".keys"


@lru_cache
def get_settings() -> Settings:
    return Settings()
