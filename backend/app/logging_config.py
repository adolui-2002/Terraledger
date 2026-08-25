"""
Structured JSON logging configuration.

Every log record emitted anywhere in the application is formatted as a
single JSON object, making it trivial to ingest into log aggregators
(ELK, Loki, CloudWatch, etc.) or grep/jq locally.

Standard fields on every record:
  timestamp   ISO-8601 UTC
  level       DEBUG | INFO | WARNING | ERROR | CRITICAL
  logger      dotted module name
  message     human-readable message
  environment APP_ENV value (development | production)

Additional fields are added by call-site context (request_id, app_id, …)
via the `extra={}` kwarg on every logger call, or by the request
middleware that injects them automatically for all HTTP-triggered logs.

Usage anywhere in the codebase:
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Pipeline started", extra={"application_id": app.id})
    logger.warning("OCR confidence low", extra={"doc_id": doc.id, "confidence": 0.31})
    logger.error("Fraud check failed", extra={"error": str(exc)}, exc_info=True)
"""
from __future__ import annotations

import logging
import logging.config
import sys

from pythonjsonlogger import jsonlogger


class _AppJsonFormatter(jsonlogger.JsonFormatter):
    """Extends the base formatter with a consistent field ordering and
    an ISO-8601 `timestamp` field (instead of the default `asctime`)."""

    def add_fields(self, log_record: dict, record: logging.LogRecord, message_dict: dict):
        super().add_fields(log_record, record, message_dict)
        # Normalise field names for downstream consumers
        log_record["timestamp"] = log_record.pop("asctime", None) or self.formatTime(record, self.datefmt)
        log_record["level"] = log_record.pop("levelname", record.levelname)
        log_record["logger"] = log_record.pop("name", record.name)
        # Remove noisy default keys we don't want
        for key in ("taskName",):
            log_record.pop(key, None)


def configure_logging(log_level: str = "INFO", environment: str = "development") -> None:
    """Call once at application startup (main.py on_startup).

    Args:
        log_level:   One of DEBUG, INFO, WARNING, ERROR, CRITICAL.
        environment: Value of APP_ENV — included in every log record.
    """
    fmt = (
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    formatter = _AppJsonFormatter(
        fmt=fmt,
        datefmt="%Y-%m-%dT%H:%M:%S.%fZ",
        static_fields={"environment": environment},
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(log_level.upper())
    # Remove any pre-existing handlers (uvicorn adds its own on import)
    root.handlers.clear()
    root.addHandler(handler)

    # Quiet down noisy third-party loggers in production
    for noisy in ("uvicorn.access", "multipart", "langdetect"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Structured logging initialised",
        extra={"log_level": log_level, "environment": environment},
    )
