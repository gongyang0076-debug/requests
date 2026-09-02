from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

import allure
import pytest

from api.product_api import ProductApi
from utils.yaml_util import load_yaml

ProductCase = dict[str, Any]
PRODUCT_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "product.yaml"
PRODUCT_DATA: dict[str, Any] = load_yaml(PRODUCT_DATA_PATH)
CREATE_SUCCESS_CASES = {
    case["case_id"]: case for case in PRODUCT_DATA["create_success"]
}
CREATE_INVALID_CASES = {
    case["case_id"]: case for case in PRODUCT_DATA["create_invalid"]
}


def _unique_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        **payload,
        "name": f"{payload['name']} {uuid4().hex[:8]}",
    }


def _assert_product(body: dict[str, Any], expected: dict[str, Any]) -> None:
    assert body["name"] == expected["name"]
    assert Decimal(str(body["price"])) == Decimal(str(expected["price"]))
    assert body["stock"] == expected["stock"]
    assert body["status"] == expected["status"]
    assert body["created_at"]


@pytest.mark.parametrize(
    "case_id",
    CREATE_SUCCESS_CASES,
    ids=list(CREATE_SUCCESS_CASES),
)
@allure.epic("接口自动化测试")
@allure.feature("商品管理")
@allure.story("创建商品")
def test_create_product(
    product_api: ProductApi,
    case_id: str,
) -> None:
    case = CREATE_SUCCESS_CASES[case_id]
    allure.dynamic.title(f"{case_id} - {case['title']}")
    payload = _unique_payload(case["request"])

    response = product_api.create_product(payload)

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
    case_id: str,
) -> None:
    case = CREATE_INVALID_CASES[case_id]
    allure.dynamic.title(f"{case_id} - {case['title']}")
    payload = _unique_payload(case["request"])

    response = product_api.create_product(payload)

    assert response.status_code == case["expected_status"]


@allure.epic("接口自动化测试")
@allure.feature("商品管理")
@allure.story("修改和删除商品")
def test_update_and_delete_product(product_api: ProductApi) -> None:
    case = PRODUCT_DATA["update"]
    allure.dynamic.title(f"{case['case_id']} - {case['title']}")
    create_payload = _unique_payload(case["create_request"])
    create_response = product_api.create_product(create_payload)
    assert create_response.status_code == 201
    product_id = create_response.json()["id"]

    update_payload = _unique_payload(case["update_request"])
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
