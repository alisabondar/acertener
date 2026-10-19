import json
import logging
import uuid

import pytest

from app.audit.log import AuditAction, AuditEntry, build_row, write_in_background
from app.db.models import User
from app.logging import JsonFormatter


class _BrokenSessionmaker:
    def __call__(self) -> "_BrokenSessionmaker":
        return self

    async def __aenter__(self) -> None:
        raise OSError("connection to host db.internal user=app failed")

    async def __aexit__(self, *_: object) -> None:
        return None


@pytest.mark.anyio
@pytest.mark.privacy
async def test_failed_background_write_is_logged_safely(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.ERROR, logger="app.audit")
    row = build_row(User(id=uuid.uuid4()), AuditEntry(AuditAction.VIEW, "patient"), "req-123")

    await write_in_background(_BrokenSessionmaker(), row)  # type: ignore[arg-type]

    [record] = caplog.records
    entry = json.loads(JsonFormatter().format(record))
    assert entry["message"] == "audit_write_failed"
    assert (entry["request_id"], entry["action"], entry["exc_type"]) == (
        "req-123",
        "view",
        "OSError",
    )
    assert "db.internal" not in caplog.text
