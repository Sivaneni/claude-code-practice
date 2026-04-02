import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

from pythonjsonlogger import json as jsonlogger

# ---------------------------------------------------------------------------
# Request-scoped correlation ID
# Set once per request by LoggingMiddleware; automatically included in every
# log record via _RequestIdFilter so ELK can group all logs for one request.
# ---------------------------------------------------------------------------
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class _ELKFormatter(jsonlogger.JsonFormatter):
    """
    Produces one JSON object per log line with ELK/Filebeat-friendly field names.

    Example output:
    {
        "@timestamp": "2026-04-02T10:30:00.123456+00:00",
        "level": "INFO",
        "logger": "app.services.weather",
        "message": "weather_api_call_success",
        "request_id": "3f2a1b...",
        "duration_ms": 231.4,
        "city_type": "by_name",
        "lookup": "London"
    }
    """

    def add_fields(
        self,
        log_record: dict,
        record: logging.LogRecord,
        message_dict: dict,
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record["@timestamp"] = datetime.now(timezone.utc).isoformat()
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["request_id"] = request_id_ctx.get("-")
        # Drop fields already captured under cleaner names
        for key in ("levelname", "name", "asctime"):
            log_record.pop(key, None)


class _RequestIdFilter(logging.Filter):
    """Stamps every log record with the active request ID."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get("-")
        return True


def setup_logging(level: str = "INFO") -> None:
    """
    Replace the root logger's handlers with a single JSON-to-stdout handler.

    Call this once at application startup (create_app).
    The level can be overridden via the LOG_LEVEL environment variable.
    """
    import os

    effective_level = os.getenv("LOG_LEVEL", level).upper()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_ELKFormatter())
    handler.addFilter(_RequestIdFilter())

    root = logging.getLogger()
    root.setLevel(effective_level)
    root.handlers = [handler]

    # Silence noisy third-party loggers that add little value in ELK
    for name in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
