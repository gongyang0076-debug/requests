from typing import Any, Mapping

import allure
from requests import Response

from common.http_client import HttpClient

UserPayload = Mapping[str, Any]


class UserApi:
    """Describe how user endpoints are called."""

    def __init__(self, client: HttpClient) -> None:
        self._client = client

    def get_user(self, user_id: int) -> Response:
        with allure.step(f"GET /users/{user_id}"):
            return self._client.get(f"/users/{user_id}")

    def create_user(self, payload: UserPayload) -> Response:
        with allure.step("POST /users/add"):
            return self._client.post("/users/add", json=payload)

    def update_user(self, user_id: int, payload: UserPayload) -> Response:
        with allure.step(f"PUT /users/{user_id}"):
            return self._client.put(f"/users/{user_id}", json=payload)

    def delete_user(self, user_id: int) -> Response:
        with allure.step(f"DELETE /users/{user_id}"):
            return self._client.delete(f"/users/{user_id}")
