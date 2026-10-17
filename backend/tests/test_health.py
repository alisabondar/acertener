import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_is_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.db
def test_health_ready_checks_the_database(client: TestClient) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_health_ready_is_503_without_leaking_connection_details(settings: Settings) -> None:
    unreachable = "postgresql+asyncpg://canary_user:canary_pw@127.0.0.1:1/canary_db"
    settings = settings.model_copy(update={"database_url": unreachable})

    with TestClient(create_app(settings)) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "SERVICE_UNAVAILABLE"
    assert "canary" not in response.text


@pytest.mark.db
def test_health_ready_is_503_when_the_database_rejects_the_connection(
    settings: Settings,
) -> None:
    missing_db = settings.database_url.rsplit("/", 1)[0] + "/canary_missing_db"

    with TestClient(create_app(settings.model_copy(update={"database_url": missing_db}))) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert "canary" not in response.text
