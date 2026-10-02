import logging
from collections.abc import Mapping
from typing import Any

REDACTED_KEYS = {
    "authorization",
    "cookie",
    "set-cookie",
    "access_token",
    "refresh_token",
    "id_token",
    "password",
    "email",
}


def redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: "[REDACTED]" if str(key).lower() in REDACTED_KEYS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, Mapping):
            record.args = redact(record.args)
        return True


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RedactingFilter())
    handler.setFormatter(
        logging.Formatter('{"level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}')
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
