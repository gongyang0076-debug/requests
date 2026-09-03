from collections.abc import Callable
from contextlib import AbstractContextManager
from decimal import Decimal
from pathlib import Path
from typing import Any

import allure
import pytest

from api.auth_api import AuthApi
from api.order_api import OrderApi
from api.product_api import ProductApi
from api.user_api import UserApi
from utils.data_factory import DataFactory
from utils.data_lifecycle import TestDataManager
from utils.yaml_util import load_yaml

ProductCase = dict[str, Any]
AuthenticatedApiFactory = Callable[
    [str],
    AbstractContextManager[tuple[UserApi, ProductApi, OrderApi]],
]
PRODUCT_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "product.yaml"
PRODUCT_DATA: dict[str, Any] = load_yaml(PRODUCT_DATA_PATH)
CREATE_SUCCESS_CASES = {
    case["case_id"]: case for case in PRODUCT_DATA["create_success"]
}
CREATE_INVALID_CASES = {
    case["case_id"]: case for case in PRODUCT_DATA["create_invalid"]
}
CREATE_SUCCESS_PARAMS = [
    pytest.param(
        case_id,
        marks=pytest.mark.smoke if case["category"] == "normal" else (),
    )
    for case_id, case in CREATE_SUCCESS_CASES.items()
]
pytestmark = [pytest.mark.product, pytest.mark.regression]


def _assert_product(body: dict[str, Any], expected: dict[str, Any]) -> None:
    assert body["name"] == expected["name"]
    assert Decimal(str(body["price"])) == Decimal(str(expected["price"]))
    assert body["stock"] == expected["stock"]
    assert body["status"] == expected["status"]
    assert body["created_at"]


@pytest.mark.parametrize(
    "case_id",
    CREATE_SUCCESS_PARAMS,
    ids=list(CREATE_SUCCESS_CASES),
)
@allure.epic("接口自动化测试")
@allure.feature("商品管理")
@allure.story("创建商品")
def test_create_product(
    product_api: ProductApi,
    data_factory: DataFactory,
    test_data: TestDataManager,
    case_id: str,
) -> None:
    case = CREATE_SUCCESS_CASES[case_id]
    allure.dynamic.title(f"{case_id} - {case['title']}")
    payload = data_factory.product_payload(case["request"])

    response = test_data.create_product(product_api, payload)

    assert response.status_code == case["expected_status"]
    product = response.json()
    _assert_product(product, payload)

    get_response = product_api.get_product(product["id"])
    assert get_response.status_code == 200
    _assert_product(get_response.json(), payload)

    list_response = product_api.list_products()
    assert list_response.status_code == 200
    assert product["id"] in {item["id"] for item in list_response.json()}

    delete_response = product_api.delete_product(product["id"])
    assert delete_response.status_code == 204


@pytest.mark.parametrize(
    "case_id",
    CREATE_INVALID_CASES,
    ids=list(CREATE_INVALID_CASES),
)
@allure.epic("接口自动化测试")
@allure.feature("商品管理")
@allure.story("非法商品参数")
def test_create_product_rejects_invalid_data(
    product_api: ProductApi,
    data_factory: DataFactory,
    test_data: TestDataManager,
    case_id: str,
) -> None:
    case = CREATE_INVALID_CASES[case_id]
    allure.dynamic.title(f"{case_id} - {case['title']}")
    payload = data_factory.product_payload(case["request"])

    response = test_data.create_product(product_api, payload)

    assert response.status_code == case["expected_status"]


@allure.epic("接口自动化测试")
@allure.feature("商品管理")
@allure.story("修改和删除商品")
def test_update_and_delete_product(
    product_api: ProductApi,
    data_factory: DataFactory,
    test_data: TestDataManager,
) -> None:
    case = PRODUCT_DATA["update"]
    allure.dynamic.title(f"{case['case_id']} - {case['title']}")
    create_payload = data_factory.product_payload(case["create_request"])
    create_response = test_data.create_product(product_api, create_payload)
    assert create_response.status_code == 201
    product_id = create_response.json()["id"]

    update_payload = data_factory.product_payload(case["update_request"])
    update_response = product_api.update_product(product_id, update_payload)
    assert update_response.status_code == case["expected_status"]
    _assert_product(update_response.json(), update_payload)

    delete_response = product_api.delete_product(product_id)
    assert delete_response.status_code == 204

    get_response = product_api.get_product(product_id)
    assert get_response.status_code == 404


@allure.epic("接口自动化测试")
@allure.feature("商品管理")
@allure.story("查询不存在商品")
def test_get_missing_product(product_api: ProductApi) -> None:
    case = PRODUCT_DATA["not_found"]
    allure.dynamic.title(f"{case['case_id']} - {case['title']}")

    response = product_api.get_product(case["product_id"])

    assert response.status_code == case["expected_status"]
    assert response.json() == {"detail": case["expected_detail"]}


@allure.epic("接口自动化测试")
@allure.feature("商品管理")
@allure.story("有关联订单的商品删除冲突")
def test_delete_product_with_existing_order_returns_409(
    auth_api: AuthApi,
    authenticated_api_factory: AuthenticatedApiFactory,
    data_factory: DataFactory,
    test_data: TestDataManager,
) -> None:
    user_payload = data_factory.user_payload("product_in_use")
    register_response = test_data.register_user(auth_api, user_payload)
    assert register_response.status_code == 201

    login_response = auth_api.login(
        {
            "username": user_payload["username"],
            "password": user_payload["password"],
        }
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    assert access_token

    with authenticated_api_factory(access_token) as (
        _user_api,
        product_api,
        order_api,
    ):
        product_response = test_data.create_product(
            product_api,
            data_factory.product_payload(
                {"name": "Product in use", "price": "18.50", "stock": 2}
            ),
        )
        assert product_response.status_code == 201
        product_id = product_response.json()["id"]

        order_response = test_data.create_order(
            order_api,
            data_factory.order_payload(product_id, quantity=1),
        )
        assert order_response.status_code == 201
        order_id = order_response.json()["id"]

        delete_response = product_api.delete_product(product_id)

        assert delete_response.status_code == 409
        assert delete_response.json() == {
            "detail": "Product cannot be deleted because it has existing orders"
        }
        assert product_api.get_product(product_id).status_code == 200
        assert order_api.get_order(order_id).status_code == 200
