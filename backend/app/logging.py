"""Structured JSON logging. Log lines carry IDs only, never PHI"""

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    """One JSON object per line. Structured fields go in `extra={"ctx": {...}}`."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        ctx = getattr(record, "ctx", None)
        if isinstance(ctx, dict):
            entry.update(ctx)
        return json.dumps(entry, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # uvicorn installs plain-text handlers before importing the app; route them through ours.
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True
    # uvicorn's access log records full URLs (query strings); our middleware replaces it.
    logging.getLogger("uvicorn.access").disabled = True
    # httpx2 logs every request's full URL at INFO, which could include identifiers.
    for name in ("httpx2", "httpcore2"):
        logging.getLogger(name).setLevel(logging.WARNING)
