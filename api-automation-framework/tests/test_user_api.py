from typing import Any

import allure
import pytest

from api.user_api import UserApi


pytestmark = [pytest.mark.user, pytest.mark.regression]


@pytest.mark.smoke
@allure.epic("接口自动化测试")
@allure.feature("用户管理")
@allure.story("查询当前用户")
def test_get_current_user(
    user_api: UserApi,
    registered_user: dict[str, Any],
) -> None:
    allure.dynamic.title("携带 JWT 查询当前用户")
    response = user_api.get_current_user()

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == registered_user["id"]
    assert body["username"] == registered_user["username"]
    assert body["email"] == registered_user["email"]


@allure.epic("接口自动化测试")
@allure.feature("用户管理")
@allure.story("未认证访问")
def test_get_current_user_without_token(public_user_api: UserApi) -> None:
    allure.dynamic.title("不携带 Token 查询当前用户")
    response = public_user_api.get_current_user()

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
