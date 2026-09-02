from typing import Any, Mapping

import allure
from requests import Response

from common.http_client import HttpClient

AuthPayload = Mapping[str, Any]


class AuthApi:
    """Describe how registration and login endpoints are called."""

    def __init__(self, client: HttpClient) -> None:
        self._client = client

    def register(self, payload: AuthPayload) -> Response:
        with allure.step("POST /api/auth/register"):
            return self._client.post("/api/auth/register", json=payload)

    def login(self, payload: AuthPayload) -> Response:
        with allure.step("POST /api/auth/login"):
            return self._client.post("/api/auth/login", json=payload)
