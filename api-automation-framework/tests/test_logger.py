import json

import pytest

from common.logger import (
    LOG_FILE,
    MASK,
    get_log_file,
    sanitize_data,
    sanitize_text,
    sanitize_url,
)


def test_get_log_file_uses_xdist_worker_id(monkeypatch) -> None:
    monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
    assert get_log_file() == LOG_FILE

    monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw2")
    assert get_log_file() == LOG_FILE.with_name("api_test_gw2.log")


def test_sanitize_data_redacts_nested_sensitive_values() -> None:
    raw_data = {
        "Authorization": "Bearer super-secret",
        "profile": {
            "password": "plain-password",
            "access_token": "access-secret",
            "name": "Tom",
        },
        "items": [{"refresh-token": "refresh-secret", "id": 1}],
        "cookies": {"session": "cookie-value"},
        "query_pairs": [("source", "test"), ("token", "pair-secret")],
    }

    sanitized = sanitize_data(raw_data)

    assert sanitized == {
        "Authorization": MASK,
        "profile": {
            "password": MASK,
            "access_token": MASK,
            "name": "Tom",
        },
        "items": [{"refresh-token": MASK, "id": 1}],
        "cookies": MASK,
        "query_pairs": [["source", "test"], ["token", MASK]],
    }


def test_sanitize_url_redacts_only_sensitive_query_parameters() -> None:
    sanitized = sanitize_url(
        "https://example.com/users?source=test&token=query-secret&password=pwd"
    )

    assert sanitized == "https://example.com/users?source=test&token=%2A%2A%2A&password=%2A%2A%2A"


def test_sanitize_text_redacts_sensitive_exception_details() -> None:
    sanitized = sanitize_text(
        "request failed: token=error-secret password: plain-password"
    )

    assert sanitized == "request failed: token=*** password: ***"


@pytest.mark.parametrize(
    "field",
    ("password", "passwd", "token", "access_token", "refresh_token",
     "Authorization", "secret", "api_key"),
)
def test_sensitive_validation_input_is_redacted(field: str) -> None:
    raw = {"detail": [{"loc": ["body", field], "input": "B1_SYNTHETIC_INPUT"}]}
    assert "B1_SYNTHETIC_INPUT" in json.dumps(raw)

    sanitized = sanitize_data(raw)

    assert sanitized["detail"][0]["input"] == "[REDACTED]"
    assert "B1_SYNTHETIC_INPUT" not in json.dumps(sanitized)
    assert raw["detail"][0]["input"] == "B1_SYNTHETIC_INPUT"


@pytest.mark.parametrize("location", (["body", "username"], [], None, "password"))
def test_non_sensitive_validation_input_is_preserved(location: object) -> None:
    raw = {"loc": location, "input": "abc"}
    assert sanitize_data(raw) == raw
