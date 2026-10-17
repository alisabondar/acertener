from typing import Any

import pytest

from app.config import Settings, validate_settings


def _settings(**fields: Any) -> Settings:
    return Settings(_env_file=None, database_url="postgresql+asyncpg://x@localhost/x", **fields)


@pytest.mark.parametrize(
    "fields",
    [{"demo_mode": True, "env": "production"}, {"demo_mode": True}],
    ids=["demo-in-production", "demo-with-env-unset"],
)
def test_demo_mode_refuses_unsafe_environments(fields: dict[str, Any]) -> None:
    with pytest.raises(RuntimeError, match="DEMO_MODE"):
        validate_settings(_settings(**fields))


@pytest.mark.parametrize("fields", [{"demo_mode": True, "env": "development"}, {}])
def test_safe_configurations_start(fields: dict[str, Any]) -> None:
    validate_settings(_settings(**fields))
