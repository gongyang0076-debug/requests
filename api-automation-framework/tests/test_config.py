import os

import pytest

from config.config import Settings, load_config


def _clear_value_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("API_BASE_URL", raising=False)
    monkeypatch.delenv("API_TIMEOUT", raising=False)


def test_load_test_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_value_overrides(monkeypatch)

    settings = load_config("test")

    assert settings == Settings(
        environment="test",
        base_url="https://dummyjson.com",
        timeout=10.0,
    )


def test_load_pre_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_value_overrides(monkeypatch)

    settings = load_config("pre")

    assert settings == Settings(
        environment="pre",
        base_url="https://dummyjson.com",
        timeout=15.0,
    )


def test_load_environment_from_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_value_overrides(monkeypatch)
    monkeypatch.setenv("TEST_ENV", "pre")

    settings = load_config()

    assert settings.environment == "pre"
    assert settings.timeout == 15.0


def test_environment_values_override_yaml(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_BASE_URL", "https://example.com")
    monkeypatch.setenv("API_TIMEOUT", "3.5")

    settings = load_config("test")

    assert settings.base_url == "https://example.com"
    assert settings.timeout == 3.5


def test_config_fixture_uses_cli_environment(
    config: Settings,
    pytestconfig: pytest.Config,
) -> None:
    cli_environment = pytestconfig.getoption("--env")

    if cli_environment is not None:
        assert config.environment == cli_environment
    else:
        assert config == load_config()
