from pathlib import Path
from typing import Any

import allure
import pytest

from api.auth_api import AuthApi
from utils.yaml_util import load_yaml

AuthCase = dict[str, Any]
AUTH_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "auth.yaml"
AUTH_DATA: dict[str, list[AuthCase]] = load_yaml(AUTH_DATA_PATH)
LOGIN_FAILURE_CASES = {
    case["case_id"]: case for case in AUTH_DATA["login_failure"]
}
pytestmark = [pytest.mark.auth, pytest.mark.regression]


@pytest.mark.smoke
@allure.epic("接口自动化测试")
@allure.feature("认证")
@allure.story("注册并登录")
def test_register_and_login(
    registered_user: dict[str, Any],
    auth_token: str,
) -> None:
    allure.dynamic.title("注册用户并获取 JWT Token")

    assert registered_user["id"] > 0
    assert registered_user["is_active"] is True
    assert auth_token


@pytest.mark.parametrize(
    "case_id",
    LOGIN_FAILURE_CASES,
    ids=list(LOGIN_FAILURE_CASES),
)
@allure.epic("接口自动化测试")
@allure.feature("认证")
@allure.story("登录失败")
def test_login_failure(
    auth_api: AuthApi,
    registered_user: dict[str, Any],
    case_id: str,
) -> None:
    case = LOGIN_FAILURE_CASES[case_id]
    allure.dynamic.title(f"{case_id} - {case['title']}")

    username_template = case["request"]["username"]
    if username_template == "$registered_user":
        username = registered_user["username"]
    else:
        username = f"missing_{registered_user['username']}"

    response = auth_api.login(
        {
            "username": username,
            "password": case["request"]["password"],
        }
    )

    assert response.status_code == case["expected_status"], (
        f"{case_id}: expected status {case['expected_status']}, "
        f"got {response.status_code}"
    )
    assert response.json()["detail"] == case["expected_detail"]
