import json
import logging
import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

MASK = "***"
LOGGER_NAME = "api_automation"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = PROJECT_ROOT / "logs" / "api_test.log"

_SENSITIVE_KEY_PARTS = (
    "authorization", "token", "password", "passwd", "secret", "apikey", "cookie",
)
_SENSITIVE_TEXT_PATTERN = re.compile(
    r"(?i)\b(authorization|access[_-]?token|refresh[_-]?token|token|password|"
    r"set-cookie|cookie)\b(\s*[:=]\s*)(?:bearer\s+)?([^\s,;&]+)"
)


def _is_sensitive_key(key: object) -> bool:
    normalized_key = re.sub(r"[^a-z0-9]", "", str(key).lower())
    return any(part in normalized_key for part in _SENSITIVE_KEY_PARTS)


def sanitize_data(value: Any) -> Any:
    """Recursively replace sensitive values while preserving useful structure."""
    if isinstance(value, Mapping):
        location = value.get("loc")
        sensitive_input = (
            isinstance(location, (list, tuple))
            and bool(location)
            and _is_sensitive_key(location[-1])
        )
        return {
            str(key): "[REDACTED]" if key == "input" and sensitive_input
            else MASK if _is_sensitive_key(key) else sanitize_data(item)
            for key, item in value.items()
        }

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        if len(value) == 2 and isinstance(value[0], str) and _is_sensitive_key(value[0]):
            return [value[0], MASK]
        return [sanitize_data(item) for item in value]

    return value


def sanitize_url(url: str) -> str:
    """Mask sensitive URL query parameter values."""
    parts = urlsplit(url)
    sanitized_query = [
        (key, MASK if _is_sensitive_key(key) else value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
    ]
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(sanitized_query), parts.fragment)
    )


def sanitize_text(value: str) -> str:
    """Mask common key-value secrets that may occur in exception messages."""
    sanitized_value = sanitize_url(value) if "://" in value else value
    return _SENSITIVE_TEXT_PATTERN.sub(rf"\1\2{MASK}", sanitized_value)


def format_json(value: Any, *, pretty: bool = False) -> str:
    """Serialize diagnostic data consistently for logs and Allure attachments."""
    return json.dumps(
        value,
        ensure_ascii=False,
        default=str,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
    )


def get_log_file() -> Path:
    """Return a process-specific log file when pytest-xdist is active."""
    worker_id = os.getenv("PYTEST_XDIST_WORKER")
    if not worker_id:
        return LOG_FILE

    safe_worker_id = re.sub(r"[^a-zA-Z0-9_-]", "_", worker_id)
    return LOG_FILE.with_name(f"api_test_{safe_worker_id}.log")


def get_logger() -> logging.Logger:
    """Return the framework logger with one console and one file handler."""
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger

    log_file = get_log_file()
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
