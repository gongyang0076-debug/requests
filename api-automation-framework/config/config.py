from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from utils.yaml_util import load_yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(__file__).with_name("config.yaml")
ENV_PATH = PROJECT_ROOT / ".env"


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str
    base_url: str
    timeout: float


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    host: str
    port: int
    user: str
    password: str = field(repr=False)
    name: str
    connect_timeout: int = 3


def load_config(environment: str | None = None) -> Settings:
    environment_values = _load_environment_values()
    selected_environment = environment or environment_values.get("TEST_ENV") or "test"
    raw_config = _load_yaml_config()

    environment_config = raw_config.get(selected_environment)
    if not isinstance(environment_config, Mapping):
        available_environments = ", ".join(sorted(raw_config))
        raise ValueError(
            f"Unknown environment '{selected_environment}'. "
            f"Available environments: {available_environments}"
        )

    base_url = environment_values.get("API_BASE_URL") or environment_config.get(
        "base_url"
    )
    if not isinstance(base_url, str) or not base_url.strip():
        raise ValueError(f"Environment '{selected_environment}' requires a base_url")

    timeout_value = environment_values.get("API_TIMEOUT") or environment_config.get(
        "timeout"
    )
    try:
        timeout = float(timeout_value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Environment '{selected_environment}' requires a numeric timeout"
        ) from error

    if timeout <= 0:
        raise ValueError(
            f"Environment '{selected_environment}' requires a positive timeout"
        )

    return Settings(
        environment=selected_environment,
        base_url=base_url.strip(),
        timeout=timeout,
    )


def load_database_config() -> DatabaseSettings:
    environment_values = _load_environment_values()
    required_names = ("DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME")
    missing_names = [
        name
        for name in required_names
        if not environment_values.get(name, "").strip()
    ]
    if missing_names:
        raise ValueError(
            "Missing database configuration: " + ", ".join(missing_names)
        )

    try:
        port = int(environment_values["DB_PORT"])
    except ValueError as error:
        raise ValueError("DB_PORT must be an integer") from error
    if not 1 <= port <= 65_535:
        raise ValueError("DB_PORT must be between 1 and 65535")

    timeout_value = environment_values.get("DB_CONNECT_TIMEOUT", "3")
    try:
        connect_timeout = int(timeout_value)
    except ValueError as error:
        raise ValueError("DB_CONNECT_TIMEOUT must be an integer") from error
    if connect_timeout <= 0:
        raise ValueError("DB_CONNECT_TIMEOUT must be greater than zero")

    return DatabaseSettings(
        host=environment_values["DB_HOST"].strip(),
        port=port,
        user=environment_values["DB_USER"].strip(),
        password=environment_values["DB_PASSWORD"],
        name=environment_values["DB_NAME"].strip(),
        connect_timeout=connect_timeout,
    )


def _load_environment_values() -> dict[str, str]:
    file_values = {
        key: value
        for key, value in dotenv_values(ENV_PATH).items()
        if value is not None
    }
    return {**file_values, **os.environ}


def _load_yaml_config() -> dict[str, Any]:
    raw_config = load_yaml(CONFIG_PATH)

    if not isinstance(raw_config, dict) or not raw_config:
        raise ValueError(f"Configuration file is empty or invalid: {CONFIG_PATH}")

    return raw_config
