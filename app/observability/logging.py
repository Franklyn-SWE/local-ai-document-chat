
"""Structured JSON logging for the RAG application."""

import json
import logging
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Format application log records as JSON."""

    ALLOWED_FIELDS = (
        "request_id",
        "duration_ms",
        "retrieval_ms",
        "inference_ms",
        "status_code",
        "error_type",
        "selected_chunks",
        "insufficient_evidence",
        "ttft_ms",
        "output_chunks",
        "inference_status",
    )

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
            "logger": record.name,
        }

        for field in self.ALLOWED_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                log_data[field] = value

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    """Configure structured application logging."""

    logger = logging.getLogger("app")
    logger.setLevel(level.upper())
    logger.propagate = False

    if logger.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
