"""
Structured logging — JSON format for production, text for development.
"""

import json
import logging
import sys
import time
from typing import Any

from app.config.settings import settings


class JSONFormatter(logging.Formatter):
    """Machine-readable JSON log lines."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
        # Attach extra fields (request_id, step, etc.)
        for key in ("request_id", "step", "duration_ms"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val
        return json.dumps(log_entry, default=str)


# ── Configure root and app loggers ────────────────────────────
_TEXT_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

logger = logging.getLogger("service_code_resolution_service")
logger.setLevel(getattr(logging, settings.log_level, logging.INFO))

_handler = logging.StreamHandler(sys.stdout)
if settings.log_format == "json":
    _handler.setFormatter(JSONFormatter())
else:
    _handler.setFormatter(logging.Formatter(_TEXT_FORMAT))

if not logger.hasHandlers():
    logger.addHandler(_handler)


def set_log_level(level: str):
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
