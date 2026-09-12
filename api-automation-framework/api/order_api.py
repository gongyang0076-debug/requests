"""订单 API 对象。

OrderApi 封装订单的创建、查询、支付、取消接口，覆盖订单状态流转：
    CREATED → PAID（支付）
    CREATED → CANCELLED（取消，库存回退）

所有接口都需要登录态。业务规则（库存不足、重复支付、越权访问等）由服务端实现，
本层只描述"接口怎么调"。
"""

from typing import Any, Mapping

import allure
from requests import Response

from common.http_client import HttpClient

# 订单请求体类型（product_id / quantity）
OrderPayload = Mapping[str, Any]


class OrderApi:
    """描述受保护的订单接口的调用方式。"""

    def __init__(self, client: HttpClient) -> None:
        self._client = client

    def create_order(self, payload: OrderPayload) -> Response:
        """POST /api/orders：创建订单。

        服务端会锁定商品记录、检查库存、计算总金额并扣减库存。
        库存不足 / 商品不存在 / 商品不可用 时返回对应错误状态码。
        """
        with allure.step("POST /api/orders"):
            return self._client.post("/api/orders", json=payload)

    def get_order(self, order_id: int) -> Response:
        """GET /api/orders/{id}：查询订单详情（含状态和金额）。"""
        with allure.step(f"GET /api/orders/{order_id}"):
            return self._client.get(f"/api/orders/{order_id}")

    def pay_order(self, order_id: int) -> Response:
        """POST /api/orders/{id}/pay：支付订单，成功后状态变为 PAID。

        重复支付、支付已取消订单会返回错误状态码。
        """
        with allure.step(f"POST /api/orders/{order_id}/pay"):
            return self._client.post(f"/api/orders/{order_id}/pay")

    def cancel_order(self, order_id: int) -> Response:
        """POST /api/orders/{id}/cancel：取消订单。

        取消 CREATED 订单会回退库存并把状态改为 CANCELLED；
        取消已支付订单会返回错误状态码。
        """
        with allure.step(f"POST /api/orders/{order_id}/cancel"):
            return self._client.post(f"/api/orders/{order_id}/cancel")
