from typing import Any, Mapping

import allure
from requests import Response

from common.http_client import HttpClient

OrderPayload = Mapping[str, Any]


class OrderApi:
    """Describe how authenticated order endpoints are called."""

    def __init__(self, client: HttpClient) -> None:
        self._client = client

    def create_order(self, payload: OrderPayload) -> Response:
        with allure.step("POST /api/orders"):
            return self._client.post("/api/orders", json=payload)

    def get_order(self, order_id: int) -> Response:
        with allure.step(f"GET /api/orders/{order_id}"):
            return self._client.get(f"/api/orders/{order_id}")

    def pay_order(self, order_id: int) -> Response:
        with allure.step(f"POST /api/orders/{order_id}/pay"):
            return self._client.post(f"/api/orders/{order_id}/pay")

    def cancel_order(self, order_id: int) -> Response:
        with allure.step(f"POST /api/orders/{order_id}/cancel"):
            return self._client.post(f"/api/orders/{order_id}/cancel")
