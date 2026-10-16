import json
import uuid
from http import HTTPStatus

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.config import Settings
from app.errors import AppError, ConflictError, NotFoundError
from app.logging import JsonFormatter
from app.main import create_app

CANARY = "CanarySmith"
PROBLEM_JSON = "application/problem+json"


class Address(BaseModel):
    zip: str


class PatientIn(BaseModel):
    dob: int
    address: Address


def _app_with_test_routes(settings: Settings) -> FastAPI:
    app = create_app(settings)

    @app.get("/raise/{kind}")
    async def raise_error(kind: str) -> None:
        errors: dict[str, AppError] = {
            "not-found": NotFoundError(),
            "conflict": ConflictError(detail="Record changed since you loaded it"),
        }
        raise errors[kind]

    @app.get("/http-401")
    async def http_401() -> None:
        raise HTTPException(status_code=401, detail=f"token for {CANARY} expired")

    @app.post("/validate")
    async def validate(_: PatientIn) -> None:
        return None

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError(f"no patient named {CANARY}")

    return app


@pytest.fixture
def error_client(settings: Settings) -> TestClient:
    return TestClient(_app_with_test_routes(settings), raise_server_exceptions=False)


def _assert_problem(response_json: dict[str, object], status: int, code: str) -> None:
    assert response_json["type"] == "about:blank"
    assert response_json["status"] == status
    assert response_json["title"] == HTTPStatus(status).phrase
    assert response_json["code"] == code
    uuid.UUID(str(response_json["request_id"]))


def test_app_error_becomes_problem_details_with_default_detail(error_client: TestClient) -> None:
    response = error_client.get("/raise/not-found")

    assert response.status_code == 404
    assert response.headers["content-type"] == PROBLEM_JSON
    body = response.json()
    _assert_problem(body, 404, "NOT_FOUND")
    assert body["detail"] == "The resource was not found."
    assert body["request_id"] == response.headers["X-Request-ID"]
    assert "errors" not in body


def test_app_error_custom_detail_overrides_the_default(error_client: TestClient) -> None:
    body = error_client.get("/raise/conflict").json()

    _assert_problem(body, 409, "CONFLICT")
    assert body["detail"] == "Record changed since you loaded it"


def test_validation_errors_use_dotted_field_keys_and_never_echo_input(
    error_client: TestClient,
) -> None:
    response = error_client.post("/validate", json={"dob": CANARY, "address": {}})

    assert response.status_code == 422
    body = response.json()
    _assert_problem(body, 422, "VALIDATION_FAILED")
    assert set(body["errors"]) == {"dob", "address.zip"}
    assert CANARY not in response.text


def test_framework_error_becomes_problem_details_and_keeps_protocol_headers(
    error_client: TestClient,
) -> None:
    response = error_client.post("/health")

    assert response.status_code == 405
    assert response.headers["content-type"] == PROBLEM_JSON
    _assert_problem(response.json(), 405, "METHOD_NOT_ALLOWED")
    assert response.headers["Allow"] == "GET"


def test_unregistered_http_status_uses_the_status_name_and_hides_detail(
    error_client: TestClient,
) -> None:
    response = error_client.get("/http-401")

    assert response.status_code == 401
    _assert_problem(response.json(), 401, "UNAUTHORIZED")
    assert CANARY not in response.text


def test_unhandled_error_is_generic_500_and_logged_without_leaking(
    error_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("DEBUG")

    response = error_client.get("/boom")

    assert response.status_code == 500
    body = response.json()
    _assert_problem(body, 500, "INTERNAL_ERROR")
    assert body["request_id"] == response.headers["X-Request-ID"]
    assert CANARY not in response.text
    assert "Traceback" not in response.text
    formatter = JsonFormatter()
    logged = [json.loads(formatter.format(r)) for r in caplog.records]
    assert all(CANARY not in json.dumps(entry) for entry in logged)
    assert any(e.get("exc_type") == "RuntimeError" for e in logged)
    assert any(e["logger"] == "app.request" and e["status"] == 500 for e in logged)
    assert all(
        e["request_id"] == body["request_id"] for e in logged if e["logger"].startswith("app.")
    )
