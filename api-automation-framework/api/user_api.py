import allure
from requests import Response

from common.http_client import HttpClient


class UserApi:
    """Describe how user endpoints are called."""

    def __init__(self, client: HttpClient) -> None:
        self._client = client

    def get_current_user(self) -> Response:
        with allure.step("GET /api/users/me"):
            return self._client.get("/api/users/me")
