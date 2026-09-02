import pytest

import config.config as config_module
from config.config import (
    DatabaseSettings,
    Settings,
    load_config,
    load_database_config,
)


def _clear_value_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("API_BASE_URL", raising=False)
    monkeypatch.delenv("API_TIMEOUT", raising=False)


def test_load_test_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_value_overrides(monkeypatch)

    settings = load_config("test")

    assert settings == Settings(
        environment="test",
        base_url="http://127.0.0.1:8000",
        timeout=10.0,
    )


def test_load_pre_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_value_overrides(monkeypatch)

    settings = load_config("pre")

    assert settings == Settings(
        environment="pre",
        base_url="http://127.0.0.1:8001",
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


def test_load_database_config_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_values = {
        "DB_HOST": "127.0.0.1",
        "DB_PORT": "3308",
        "DB_USER": "api_test_user",
        "DB_PASSWORD": "local_test_password",
        "DB_NAME": "api_test",
        "DB_CONNECT_TIMEOUT": "5",
    }
    monkeypatch.setattr(
        config_module,
        "_load_environment_values",
        lambda: database_values,
    )

    settings = load_database_config()

    assert settings == DatabaseSettings(
        host="127.0.0.1",
        port=3308,
        user="api_test_user",
        password="local_test_password",
        name="api_test",
        connect_timeout=5,
    )
    assert "local_test_password" not in repr(settings)


def test_load_database_config_reports_missing_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config_module, "_load_environment_values", lambda: {})

    with pytest.raises(ValueError, match="Missing database configuration"):
        load_database_config()
