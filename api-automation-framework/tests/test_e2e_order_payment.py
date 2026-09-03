from collections.abc import Callable
from contextlib import AbstractContextManager
from decimal import Decimal

import allure
import pytest

from api.auth_api import AuthApi
from api.order_api import OrderApi
from api.product_api import ProductApi
from api.user_api import UserApi
from common.database import DatabaseClient
from common.logger import format_json
from utils.data_factory import DataFactory
from utils.data_lifecycle import TestDataManager

AuthenticatedApiFactory = Callable[
    [str],
    AbstractContextManager[tuple[UserApi, ProductApi, OrderApi]],
]
pytestmark = [pytest.mark.regression, pytest.mark.e2e, pytest.mark.db]


@allure.epic("接口自动化测试")
@allure.feature("端到端业务链路")
@allure.story("注册到订单支付")
def test_register_to_paid_order_e2e(
    auth_api: AuthApi,
    authenticated_api_factory: AuthenticatedApiFactory,
    database_client: DatabaseClient,
    data_factory: DataFactory,
    test_data: TestDataManager,
) -> None:
    user_payload = data_factory.user_payload("e2e")

    with allure.step("注册动态用户"):
        register_response = test_data.register_user(auth_api, user_payload)
        assert register_response.status_code == 201
        registered_user = register_response.json()
        user_id = registered_user["id"]
        assert registered_user["username"] == user_payload["username"]

    with allure.step("登录并动态获取 JWT"):
        login_response = auth_api.login(
            {
                "username": user_payload["username"],
                "password": user_payload["password"],
            }
        )
        assert login_response.status_code == 200
        token_body = login_response.json()
        assert token_body["token_type"] == "bearer"
        access_token = token_body["access_token"]
        assert access_token

    with authenticated_api_factory(access_token) as (
        user_api,
        product_api,
        order_api,
    ):
        with allure.step("使用 Token 查询当前用户"):
            me_response = user_api.get_current_user()
            assert me_response.status_code == 200
            assert me_response.json()["id"] == user_id

        with allure.step("创建商品并动态获取 Product ID"):
            product_response = test_data.create_product(
                product_api,
                data_factory.product_payload(
                    {
                        "name": "E2E Product",
                        "price": "29.90",
                        "stock": 3,
                        "status": "ACTIVE",
                    }
                ),
            )
            assert product_response.status_code == 201
            product = product_response.json()
            product_id = product["id"]
            assert product_id > 0

        with allure.step("创建订单并动态获取 Order ID"):
            create_order_response = test_data.create_order(
                order_api,
                data_factory.order_payload(product_id, quantity=2),
            )
            assert create_order_response.status_code == 201
            order = create_order_response.json()
            order_id = order["id"]
            assert order_id > 0
            assert order["user_id"] == user_id
            assert order["product_id"] == product_id
            assert order["status"] == "CREATED"
            assert Decimal(order["total_amount"]) == Decimal("59.80")

        with allure.step("支付前查询订单状态"):
            before_payment_response = order_api.get_order(order_id)
            assert before_payment_response.status_code == 200
            assert before_payment_response.json()["status"] == "CREATED"

        with allure.step("支付订单"):
            pay_response = order_api.pay_order(order_id)
            assert pay_response.status_code == 200
            assert pay_response.json()["status"] == "PAID"

        with allure.step("支付后再次查询订单和库存"):
            paid_order_response = order_api.get_order(order_id)
            assert paid_order_response.status_code == 200
            paid_order = paid_order_response.json()
            assert paid_order["id"] == order_id
            assert paid_order["status"] == "PAID"

            product_after_order_response = product_api.get_product(product_id)
            assert product_after_order_response.status_code == 200
            assert product_after_order_response.json()["stock"] == 1

        with allure.step("查询 MySQL 验证订单关键状态"):
            database_order = database_client.fetch_one(
                "SELECT status FROM orders WHERE id = %s",
                (order_id,),
            )
            allure.attach(
                format_json(
                    {
                        "query": "SELECT status FROM orders WHERE id = %s",
                        "params": [order_id],
                        "result": database_order,
                    },
                    pretty=True,
                ),
                name="MySQL Order Status",
                attachment_type=allure.attachment_type.JSON,
            )
            assert database_order is not None
            assert database_order["status"] == "PAID"
