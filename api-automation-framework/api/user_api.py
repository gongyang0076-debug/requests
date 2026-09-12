"""用户 API 对象。

UserApi 封装"获取当前登录用户信息"接口，需要登录态（Bearer Token 由
Fixture 注入到 HttpClient 的 Session Header 里）。
"""

import allure
from requests import Response

from common.http_client import HttpClient


class UserApi:
    """描述用户相关接口的调用方式。"""

    def __init__(self, client: HttpClient) -> None:
        self._client = client

    def get_current_user(self) -> Response:
        """GET /api/users/me：获取当前登录用户的资料。

        该接口受 JWT 保护，未带或带错 Token 会返回 401，常用于验证登录态。
        """
        with allure.step("GET /api/users/me"):
            return self._client.get("/api/users/me")
