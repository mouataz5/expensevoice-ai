"""
Structured logging for production (Part 3.2).
Configures JSON format with timestamp, level, message, request_id when available.
"""
import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

# Request ID for correlation (set by middleware)
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    return request_id_ctx.get()


class StructuredFormatter(logging.Formatter):
    """JSON log line: timestamp, level, message, request_id, and any extra fields."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        rid = get_request_id()
        if rid:
            log_obj["request_id"] = rid
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        # Extra attributes (e.g. from logger.info("msg", extra={"user_id": "..."}))
        for key, value in record.__dict__.items():
            if key not in (
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "exc_info", "exc_text", "thread", "threadName",
                "message", "taskName",
            ) and value is not None:
                log_obj[key] = value
        return json.dumps(log_obj, default=str)


def setup_structured_logging(
    level: str | int = logging.INFO,
    json_logs: bool = True,
) -> None:
    """
    Configure root logger to use structured (JSON) output.
    Set JSON_LOGS=false to use plain text instead.
    """
    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        if json_logs:
            handler.setFormatter(StructuredFormatter())
        else:
            handler.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
            )
        root.addHandler(handler)
