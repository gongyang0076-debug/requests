from decimal import Decimal
from pathlib import Path
from typing import Any

import allure
import pytest

from api.order_api import OrderApi
from api.product_api import ProductApi
from utils.data_factory import DataFactory
from utils.data_lifecycle import TestDataManager
from utils.yaml_util import load_yaml

ORDER_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "order.yaml"
ORDER_DATA: dict[str, Any] = load_yaml(ORDER_DATA_PATH)
INVALID_QUANTITY_CASES = {
    case["case_id"]: case for case in ORDER_DATA["invalid_quantity"]
}
pytestmark = [pytest.mark.order, pytest.mark.regression]


def _create_product(
    test_data: TestDataManager,
    data_factory: DataFactory,
    product_api: ProductApi,
    payload: dict[str, Any],
) -> dict[str, Any]:
    unique_payload = data_factory.product_payload(payload)
    response = test_data.create_product(product_api, unique_payload)
    assert response.status_code == 201
    return response.json()


def _create_order(
    test_data: TestDataManager,
    data_factory: DataFactory,
    order_api: OrderApi,
    product_id: int,
    quantity: int,
) -> dict[str, Any]:
    response = test_data.create_order(
        order_api,
        data_factory.order_payload(product_id, quantity),
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.smoke
@allure.epic("接口自动化测试")
@allure.feature("订单管理")
@allure.story("创建并查询订单")
def test_create_and_get_order(
    product_api: ProductApi,
    order_api: OrderApi,
    registered_user: dict[str, Any],
    data_factory: DataFactory,
    test_data: TestDataManager,
) -> None:
    case = ORDER_DATA["create_success"]
    allure.dynamic.title(f"{case['case_id']} - {case['title']}")
    product = _create_product(test_data, data_factory, product_api, case["product"])

    order = _create_order(
        test_data,
        data_factory,
        order_api,
        product["id"],
        case["request"]["quantity"],
    )

    assert order["user_id"] == registered_user["id"]
    assert order["product_id"] == product["id"]
    assert order["quantity"] == case["request"]["quantity"]
    assert Decimal(str(order["total_amount"])) == Decimal(
        str(case["expected_total_amount"])
    )
    assert order["status"] == case["expected_order_status"]

    response = order_api.get_order(order["id"])
    assert response.status_code == 200
    assert response.json()["id"] == order["id"]
    assert response.json()["status"] == "CREATED"


@allure.epic("接口自动化测试")
@allure.feature("订单管理")
@allure.story("支付状态流转")
def test_pay_order_and_reject_repeated_operations(
    product_api: ProductApi,
    order_api: OrderApi,
    data_factory: DataFactory,
    test_data: TestDataManager,
) -> None:
    case = ORDER_DATA["pay"]
    allure.dynamic.title(f"{case['case_id']} - {case['title']}")
    product = _create_product(test_data, data_factory, product_api, case["product"])
    order = _create_order(
        test_data,
        data_factory,
        order_api,
        product["id"],
        case["request"]["quantity"],
    )

    pay_response = order_api.pay_order(order["id"])
    assert pay_response.status_code == 200
    assert pay_response.json()["status"] == case["expected_status"]

    get_response = order_api.get_order(order["id"])
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "PAID"

    repeated_pay_response = order_api.pay_order(order["id"])
    assert repeated_pay_response.status_code == case["repeated_pay_status"]
    assert repeated_pay_response.json() == {
        "detail": "Order cannot be paid when status is PAID"
    }

    cancel_response = order_api.cancel_order(order["id"])
    assert cancel_response.status_code == case["cancel_paid_status"]
    assert cancel_response.json() == {
        "detail": "Order cannot be cancelled when status is PAID"
    }


@allure.epic("接口自动化测试")
@allure.feature("订单管理")
@allure.story("取消状态流转")
def test_cancel_order_restores_stock(
    product_api: ProductApi,
    order_api: OrderApi,
    data_factory: DataFactory,
    test_data: TestDataManager,
) -> None:
    case = ORDER_DATA["cancel"]
    allure.dynamic.title(f"{case['case_id']} - {case['title']}")
    product = _create_product(test_data, data_factory, product_api, case["product"])
    order = _create_order(
        test_data,
        data_factory,
        order_api,
        product["id"],
        case["request"]["quantity"],
    )

    cancel_response = order_api.cancel_order(order["id"])
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == case["expected_status"]

    product_response = product_api.get_product(product["id"])
    assert product_response.status_code == 200
    assert product_response.json()["stock"] == case["product"]["stock"]

    pay_response = order_api.pay_order(order["id"])
    assert pay_response.status_code == case["pay_cancelled_status"]
    assert pay_response.json() == {
        "detail": "Order cannot be paid when status is CANCELLED"
    }


@allure.epic("接口自动化测试")
@allure.feature("订单管理")
@allure.story("库存不足")
def test_create_order_rejects_insufficient_stock(
    product_api: ProductApi,
    order_api: OrderApi,
    data_factory: DataFactory,
    test_data: TestDataManager,
) -> None:
    case = ORDER_DATA["insufficient_stock"]
    allure.dynamic.title(f"{case['case_id']} - {case['title']}")
    product = _create_product(test_data, data_factory, product_api, case["product"])

    response = test_data.create_order(
        order_api,
        data_factory.order_payload(
            product["id"],
            case["request"]["quantity"],
        ),
    )

    assert response.status_code == case["expected_status"]
    assert response.json() == {"detail": case["expected_detail"]}


@allure.epic("接口自动化测试")
@allure.feature("订单管理")
@allure.story("商品不存在")
def test_create_order_rejects_missing_product(order_api: OrderApi) -> None:
    case = ORDER_DATA["missing_product"]
    allure.dynamic.title(f"{case['case_id']} - {case['title']}")

    response = order_api.create_order(
        {
            "product_id": case["product_id"],
            "quantity": case["request"]["quantity"],
        }
    )

    assert response.status_code == case["expected_status"]
    assert response.json() == {"detail": case["expected_detail"]}


@pytest.mark.parametrize(
    "case_id",
    INVALID_QUANTITY_CASES,
    ids=list(INVALID_QUANTITY_CASES),
)
@allure.epic("接口自动化测试")
@allure.feature("订单管理")
@allure.story("非法购买数量")
def test_create_order_rejects_invalid_quantity(
    product_api: ProductApi,
    order_api: OrderApi,
    data_factory: DataFactory,
    test_data: TestDataManager,
    case_id: str,
) -> None:
    case = INVALID_QUANTITY_CASES[case_id]
    allure.dynamic.title(f"{case_id} - {case['title']}")
    product = _create_product(
        test_data,
        data_factory,
        product_api,
        {"name": "Quantity Product", "price": 10.00, "stock": 5},
    )

    response = test_data.create_order(
        order_api,
        data_factory.order_payload(product["id"], case["quantity"]),
    )

    assert response.status_code == case["expected_status"]


@allure.epic("接口自动化测试")
@allure.feature("订单管理")
@allure.story("订单不存在")
def test_get_missing_order(order_api: OrderApi) -> None:
    case = ORDER_DATA["missing_order"]
    allure.dynamic.title(f"{case['case_id']} - {case['title']}")

    response = order_api.get_order(case["order_id"])

    assert response.status_code == case["expected_status"]
    assert response.json() == {"detail": case["expected_detail"]}
