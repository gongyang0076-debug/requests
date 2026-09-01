from pathlib import Path
from typing import Any

import pytest
from requests import Response

from api.user_api import UserApi
from utils.yaml_util import load_yaml

UserCase = dict[str, Any]
USER_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "user.yaml"
USER_CASES: dict[str, list[UserCase]] = load_yaml(USER_DATA_PATH)


def _assert_response(response: Response, case: UserCase) -> None:
    assert response.status_code == case["expected_status"], case["title"]

    body = response.json()
    for field, expected_value in case.get("expected_body", {}).items():
        assert body.get(field) == expected_value, case["title"]

    for field in case.get("expected_non_empty_fields", []):
        assert field in body, case["title"]
        assert body[field], case["title"]

    for field, expected_fragment in case.get("expected_contains", {}).items():
        assert expected_fragment in body[field], case["title"]


@pytest.mark.parametrize(
    "case",
    USER_CASES["get_user"],
    ids=lambda case: case["case_id"],
)
def test_get_user(user_api: UserApi, case: UserCase) -> None:
    response = user_api.get_user(case["request"]["user_id"])

    _assert_response(response, case)


@pytest.mark.parametrize(
    "case",
    USER_CASES["create_user"],
    ids=lambda case: case["case_id"],
)
def test_create_user(user_api: UserApi, case: UserCase) -> None:
    response = user_api.create_user(case["request"])

    _assert_response(response, case)


@pytest.mark.parametrize(
    "case",
    USER_CASES["update_user"],
    ids=lambda case: case["case_id"],
)
def test_update_user(user_api: UserApi, case: UserCase) -> None:
    request_data = case["request"]
    response = user_api.update_user(
        request_data["user_id"],
        request_data["payload"],
    )

    _assert_response(response, case)


@pytest.mark.parametrize(
    "case",
    USER_CASES["delete_user"],
    ids=lambda case: case["case_id"],
)
def test_delete_user(user_api: UserApi, case: UserCase) -> None:
    response = user_api.delete_user(case["request"]["user_id"])

    _assert_response(response, case)
