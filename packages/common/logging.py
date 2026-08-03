"""Structured JSON logging for BK Foundry.

One factory — ``get_logger`` — returns a stdlib logger that emits exactly one
JSON object per line. Every program logs in this format, so runs across the
scraper, PDF worker, engine and field app stay greppable and machine-readable.
A correlation id (per job or per request) can be bound so every line emitted
for one unit of work shares the same id.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    """Render a log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        correlation_id = getattr(record, "correlation_id", None)
        if correlation_id is not None:
            payload["correlation_id"] = correlation_id
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def get_logger(
    name: str, *, correlation_id: str | None = None
) -> logging.LoggerAdapter:
    """Return a JSON logger for ``name``.

    Attaches a single stdout handler with the JSON formatter (idempotently, so
    repeated calls do not stack duplicate handlers). If ``correlation_id`` is
    given, every record from the returned adapter carries it, so all logs for
    one job or request can be traced together.
    """
    logger = logging.getLogger(name)
    if not any(isinstance(h.formatter, JsonFormatter) for h in logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logging.LoggerAdapter(logger, {"correlation_id": correlation_id})
