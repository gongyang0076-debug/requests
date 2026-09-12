"""健康检查 API 对象。

HealthApi 封装服务的健康检查接口，通常在 Smoke / CI 启动阶段用于确认
被测服务是否可用、数据库连接是否正常。
"""

import allure
from requests import Response

from common.http_client import HttpClient


class HealthApi:
    """描述服务健康检查接口的调用方式。"""

    def __init__(self, client: HttpClient) -> None:
        self._client = client

    def get_health(self) -> Response:
        """GET /health：服务存活检查，返回 200 表示服务在线。"""
        with allure.step("GET /health"):
            return self._client.get("/health")
