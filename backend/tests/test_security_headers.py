from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, validate_settings
from app.main import create_app

FRONTEND = "http://localhost:5173"


@pytest.fixture
def web(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as client:
        yield client


def test_allowed_origin_may_send_the_persona_header(web: TestClient) -> None:
    response = web.options(
        "/api/v1/patients",
        headers={
            "Origin": FRONTEND,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-persona",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == FRONTEND
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "x-persona" in response.headers["access-control-allow-headers"].lower()


def test_other_origins_get_no_cors_grant(web: TestClient) -> None:
    response = web.get("/health", headers={"Origin": "https://evil.example"})

    assert "access-control-allow-origin" not in response.headers


def test_origins_come_from_a_comma_separated_env_value() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://x@h/x",
        cors_origins="http://a.test, http://b.test",
    )

    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_wildcard_origin_is_refused() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://x@h/x",
        cors_origins="*",
    )

    with pytest.raises(RuntimeError, match="CORS"):
        validate_settings(settings)


def test_api_responses_are_never_cached_and_lock_down_the_browser(web: TestClient) -> None:
    headers = web.get("/health").headers

    assert headers["cache-control"] == "no-store"
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "no-referrer"
    assert headers["x-frame-options"] == "DENY"
    assert headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert "strict-transport-security" not in headers


def test_docs_still_load_their_assets(web: TestClient) -> None:
    response = web.get("/docs")

    assert response.status_code == 200
    assert "cdn.jsdelivr.net" in response.headers["content-security-policy"]


def test_hsts_only_in_production(settings: Settings) -> None:
    production = settings.model_copy(update={"env": "production"})

    with TestClient(create_app(production)) as client:
        headers = client.get("/health").headers

    assert headers["strict-transport-security"].startswith("max-age=")


def test_crashes_still_carry_cors_and_security_headers(settings: Settings) -> None:
    app = create_app(settings)

    @app.get("/test/crash")
    async def crash() -> None:
        raise RuntimeError("boom")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/test/crash", headers={"Origin": FRONTEND})

    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_ERROR"
    assert response.headers["access-control-allow-origin"] == FRONTEND
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"] == response.json()["request_id"]
