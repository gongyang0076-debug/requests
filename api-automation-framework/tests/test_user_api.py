from pathlib import Path
from typing import Any

import allure
import pytest
from requests import Response

from api.user_api import UserApi
from utils.yaml_util import load_yaml

UserCase = dict[str, Any]
USER_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "user.yaml"
USER_CASES: dict[str, list[UserCase]] = load_yaml(USER_DATA_PATH)


def _assert_response(response: Response, case: UserCase) -> None:
    case_name = f"{case['case_id']} - {case['title']}"
    assert response.status_code == case["expected_status"], (
        f"{case_name}: expected status {case['expected_status']}, "
        f"got {response.status_code}"
    )

    body = response.json()
    for field, expected_value in case.get("expected_body", {}).items():
        assert body.get(field) == expected_value, (
            f"{case_name}: field {field!r} expected {expected_value!r}, "
            f"got {body.get(field)!r}"
        )

    for field in case.get("expected_non_empty_fields", []):
        assert field in body, f"{case_name}: missing field {field!r}"
        assert body[field], f"{case_name}: field {field!r} must not be empty"

    for field, expected_fragment in case.get("expected_contains", {}).items():
        assert field in body, f"{case_name}: missing field {field!r}"
        assert expected_fragment in body[field], (
            f"{case_name}: field {field!r} does not contain {expected_fragment!r}"
        )


@pytest.mark.parametrize(
    "case",
    USER_CASES["get_user"],
    ids=lambda case: case["case_id"],
)
@allure.epic("接口自动化测试")
@allure.feature("用户管理")
@allure.story("查询用户")
def test_get_user(user_api: UserApi, case: UserCase) -> None:
    allure.dynamic.title(f"{case['case_id']} - {case['title']}")
    response = user_api.get_user(case["request"]["user_id"])

    _assert_response(response, case)


@pytest.mark.parametrize(
    "case",
    USER_CASES["create_user"],
    ids=lambda case: case["case_id"],
)
@allure.epic("接口自动化测试")
@allure.feature("用户管理")
@allure.story("创建用户")
def test_create_user(user_api: UserApi, case: UserCase) -> None:
    allure.dynamic.title(f"{case['case_id']} - {case['title']}")
    response = user_api.create_user(case["request"])

    _assert_response(response, case)


@pytest.mark.parametrize(
    "case",
    USER_CASES["update_user"],
    ids=lambda case: case["case_id"],
)
@allure.epic("接口自动化测试")
@allure.feature("用户管理")
@allure.story("更新用户")
def test_update_user(user_api: UserApi, case: UserCase) -> None:
    allure.dynamic.title(f"{case['case_id']} - {case['title']}")
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
@allure.epic("接口自动化测试")
@allure.feature("用户管理")
@allure.story("删除用户")
def test_delete_user(user_api: UserApi, case: UserCase) -> None:
    allure.dynamic.title(f"{case['case_id']} - {case['title']}")
    response = user_api.delete_user(case["request"]["user_id"])

    _assert_response(response, case)
