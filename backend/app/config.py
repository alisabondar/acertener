from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    env: Literal["development", "test", "production"] = "development"
    demo_mode: bool = False
    inactive_after_years: int = 3
    # "Today" (today's visits, ages, inactivity) means the practice's calendar day.
    practice_timezone: str = "America/New_York"
    # Browser origins allowed to call the API with credentials. Comma-separated; never "*".
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    # AI summaries: "auto" uses Gemini when a key is set, otherwise the deterministic mock.
    summary_provider: Literal["auto", "mock", "gemini"] = "auto"
    gemini_api_key: SecretStr | None = None
    # Google keeps this alias on its current Flash model, so a retired version can't break us.
    gemini_model: str = "gemini-flash-latest"
    gemini_requests_per_minute: int = 10
    # How long after the last clinical change a viewed summary waits before regenerating.
    summary_debounce_seconds: int = 15

    database_url: str
    keys_dir: Path = REPO_ROOT / ".keys"


def validate_settings(settings: Settings) -> None:
    """Refuse configurations that would expose the demo persona picker somewhere real."""
    if settings.demo_mode and (
        settings.env == "production" or "env" not in settings.model_fields_set
    ):
        raise RuntimeError("DEMO_MODE=true needs ENV set explicitly to development or test")
    if "*" in settings.cors_origins:
        # With credentials allowed, a wildcard would let any website read patient data.
        raise RuntimeError("CORS_ORIGINS must list origins explicitly; '*' isn't allowed")


@lru_cache
def get_settings() -> Settings:
    return Settings()
