from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
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
