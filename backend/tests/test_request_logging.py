import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.logging import JsonFormatter

REQUEST_LOGGER = "app.request"


def _request_logs(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    formatter = JsonFormatter()
    return [json.loads(formatter.format(r)) for r in caplog.records if r.name == REQUEST_LOGGER]


def test_valid_incoming_request_id_is_reused(client: TestClient) -> None:
    incoming = str(uuid.uuid4())

    response = client.get("/health", headers={"X-Request-ID": incoming})

    assert response.headers["X-Request-ID"] == incoming


def test_invalid_incoming_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "evil\ninjected log line"})

    request_id = response.headers["X-Request-ID"]
    assert "evil" not in request_id
    uuid.UUID(request_id)


def test_request_is_logged_as_json_with_request_id(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("INFO", logger=REQUEST_LOGGER)

    response = client.get("/health")

    [entry] = _request_logs(caplog)
    assert entry["request_id"] == response.headers["X-Request-ID"]
    assert entry["method"] == "GET"
    assert entry["route"] == "/health"
    assert entry["status"] == 200
    assert isinstance(entry["duration_ms"], float)


def test_query_string_never_reaches_logs(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("DEBUG")

    client.get("/health?name=CanarySmith")

    formatter = JsonFormatter()
    assert all("CanarySmith" not in formatter.format(r) for r in caplog.records)
    assert _request_logs(caplog), "expected a request log line"
