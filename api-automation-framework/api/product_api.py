"""商品 API 对象。

ProductApi 封装商品的增删改查接口。这些接口都需要登录态（Bearer Token）。
业务规则（如已存在订单时不能删除商品返回 409）由服务端实现，
本层只负责把请求发出去并返回响应。
"""

from typing import Any, Mapping

import allure
from requests import Response

from common.http_client import HttpClient

# 商品请求体类型（name / price / stock / status 等字段）
ProductPayload = Mapping[str, Any]


class ProductApi:
    """描述受保护的商品接口的调用方式。"""

    def __init__(self, client: HttpClient) -> None:
        self._client = client

    def create_product(self, payload: ProductPayload) -> Response:
        """POST /api/products：创建商品。"""
        with allure.step("POST /api/products"):
            return self._client.post("/api/products", json=payload)

    def get_product(self, product_id: int) -> Response:
        """GET /api/products/{id}：查询单个商品。"""
        with allure.step(f"GET /api/products/{product_id}"):
            return self._client.get(f"/api/products/{product_id}")

    def list_products(self) -> Response:
        """GET /api/products：查询商品列表（暂未分页）。"""
        with allure.step("GET /api/products"):
            return self._client.get("/api/products")

    def update_product(self, product_id: int, payload: ProductPayload) -> Response:
        """PUT /api/products/{id}：更新商品（全量更新）。"""
        with allure.step(f"PUT /api/products/{product_id}"):
            return self._client.put(f"/api/products/{product_id}", json=payload)

    def delete_product(self, product_id: int) -> Response:
        """DELETE /api/products/{id}：删除商品。

        若商品已有订单引用，服务端返回 409；清理阶段遇到 404 视为已删除。
        """
        with allure.step(f"DELETE /api/products/{product_id}"):
            return self._client.delete(f"/api/products/{product_id}")
