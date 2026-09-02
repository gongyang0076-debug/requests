from typing import Any, Mapping

import allure
from requests import Response

from common.http_client import HttpClient

ProductPayload = Mapping[str, Any]


class ProductApi:
    """Describe how authenticated product endpoints are called."""

    def __init__(self, client: HttpClient) -> None:
        self._client = client

    def create_product(self, payload: ProductPayload) -> Response:
        with allure.step("POST /api/products"):
            return self._client.post("/api/products", json=payload)

    def get_product(self, product_id: int) -> Response:
        with allure.step(f"GET /api/products/{product_id}"):
            return self._client.get(f"/api/products/{product_id}")

    def list_products(self) -> Response:
        with allure.step("GET /api/products"):
            return self._client.get("/api/products")

    def update_product(self, product_id: int, payload: ProductPayload) -> Response:
        with allure.step(f"PUT /api/products/{product_id}"):
            return self._client.put(f"/api/products/{product_id}", json=payload)

    def delete_product(self, product_id: int) -> Response:
        with allure.step(f"DELETE /api/products/{product_id}"):
            return self._client.delete(f"/api/products/{product_id}")
