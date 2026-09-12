"""认证 API 对象。

AuthApi 把"注册 / 登录"两个接口的路径和 HTTP 方法封装成业务方法，
测试用例直接调用 register / login，不用关心具体 URL 拼接。
业务断言仍由测试层负责，本层只描述"接口怎么调"。
"""

from typing import Any, Mapping

import allure
from requests import Response

from common.http_client import HttpClient

# 认证请求体类型（username / email / password 等字段）
AuthPayload = Mapping[str, Any]


class AuthApi:
    """描述注册和登录接口的调用方式。"""

    def __init__(self, client: HttpClient) -> None:
        # 传入已配置好 base_url / timeout 的 HttpClient
        self._client = client

    def register(self, payload: AuthPayload) -> Response:
        """POST /api/auth/register：注册新用户。"""
        with allure.step("POST /api/auth/register"):
            # allure.step 让 Allure 报告里出现这一步，便于追踪
            return self._client.post("/api/auth/register", json=payload)

    def login(self, payload: AuthPayload) -> Response:
        """POST /api/auth/login：登录并返回 JWT。"""
        with allure.step("POST /api/auth/login"):
            return self._client.post("/api/auth/login", json=payload)
