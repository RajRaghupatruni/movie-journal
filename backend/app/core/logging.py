import json
import logging
import logging.config
from contextvars import ContextVar
from datetime import UTC, datetime

request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", request_id.get()),
        }
        for field in (
            "method",
            "route",
            "status_code",
            "duration_ms",
            "error_class",
            "provider",
            "dbapi_error_class",
            "sqlstate",
            "sqlstate_category",
            "connection_invalidated",
        ):
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        # Deliberately omit exception strings, SQL, URLs, request bodies and headers.
        return json.dumps(payload)


def configure_logging(level: str) -> None:
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"json": {"()": JsonFormatter}},
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                    "stream": "ext://sys.stdout",
                }
            },
            "root": {"handlers": ["console"], "level": level},
            "loggers": {
                "uvicorn": {"handlers": ["console"], "level": level, "propagate": False},
                "uvicorn.access": {"handlers": [], "propagate": False},
                "sqlalchemy.engine": {"level": "WARNING"},
            },
        }
    )
