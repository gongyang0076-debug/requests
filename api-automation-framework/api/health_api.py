import allure
from requests import Response

from common.http_client import HttpClient


class HealthApi:
    """Describe how the service health endpoint is called."""

    def __init__(self, client: HttpClient) -> None:
        self._client = client

    def get_health(self) -> Response:
        with allure.step("GET /health"):
            return self._client.get("/health")
