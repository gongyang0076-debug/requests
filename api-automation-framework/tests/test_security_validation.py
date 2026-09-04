from collections.abc import Callable
from contextlib import AbstractContextManager
import io
import json
import logging
from pathlib import Path
from typing import Any

import allure
import pytest
from requests import Response

from api.auth_api import AuthApi
from api.order_api import OrderApi
from api.product_api import ProductApi
from api.user_api import UserApi
from common.database import DatabaseClient
from common.logger import get_logger, sanitize_data
from utils.data_factory import DataFactory
from utils.data_lifecycle import TestDataManager
from utils.yaml_util import load_yaml

SecurityCase = dict[str, Any]
AuthenticatedApiFactory = Callable[
    [str],
    AbstractContextManager[tuple[UserApi, ProductApi, OrderApi]],
]
SECURITY_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "security.yaml"
SECURITY_DATA: dict[str, list[SecurityCase]] = load_yaml(SECURITY_DATA_PATH)
AUTH_REGISTRATION_CASES = {
    case["case_id"]: case for case in SECURITY_DATA["auth_registration_invalid"]
}
AUTH_LOGIN_CASES = {
    case["case_id"]: case for case in SECURITY_DATA["auth_login_security"]
}
PRODUCT_INVALID_CASES = {
    case["case_id"]: case for case in SECURITY_DATA["product_invalid"]
}
ORDER_INVALID_CASES = {
    case["case_id"]: case for case in SECURITY_DATA["order_invalid"]
}
PLACEHOLDERS: dict[str, Any] = {
    "$overlong_username": "u" * 51,
    "$overlong_product_name": "P" * 101,
}
pytestmark = pytest.mark.regression


def _resolve_payload(
    template: dict[str, Any],
    **dynamic_values: Any,
) -> dict[str, Any]:
    values = {**PLACEHOLDERS, **dynamic_values}
    return {
        key: values.get(value, value) if isinstance(value, str) else value
        for key, value in template.items()
    }


def _assert_validation_error(response: Response, case: SecurityCase) -> None:
    assert response.status_code == case["expected_status"], (
        f"{case['case_id']}: expected {case['expected_status']}, "
        f"got {response.status_code}"
    )
    details = response.json()["detail"]
    assert any(error["loc"][-1] == case["expected_field"] for error in details), (
        f"{case['case_id']}: expected validation error for "
        f"{case['expected_field']}, got {details}"
    )


@pytest.mark.auth
@pytest.mark.parametrize(
    "case_id",
    AUTH_REGISTRATION_CASES,
    ids=list(AUTH_REGISTRATION_CASES),
)
@allure.epic("接口自动化测试")
@allure.feature("异常与安全输入")
@allure.story("注册参数校验")
def test_registration_rejects_invalid_payload(
    auth_api: AuthApi,
    test_data: TestDataManager,
    case_id: str,
) -> None:
    case = AUTH_REGISTRATION_CASES[case_id]
    allure.dynamic.title(f"{case_id} - {case['title']}")
    payload = _resolve_payload(case["request"])

    response = test_data.register_user(auth_api, payload)

    _assert_validation_error(response, case)


@pytest.mark.auth
@pytest.mark.parametrize("case_id", ("password_too_short", "password_too_long"))
@allure.epic("接口自动化测试")
@allure.feature("异常与安全输入")
@allure.story("422 敏感校验输入脱敏")
def test_registration_validation_password_is_redacted(
    auth_api: AuthApi,
    data_factory: DataFactory,
    test_data: TestDataManager,
    monkeypatch: pytest.MonkeyPatch,
    case_id: str,
) -> None:
    # Parametrize by case ID, not by password: Allure parameters stay non-sensitive.
    password = "B1shrt!" if case_id == "password_too_short" else "B1_LONG_SYNTHETIC_" + "x" * 129
    expected_type = "string_too_short" if case_id == "password_too_short" else "string_too_long"
    payload = data_factory.user_payload("validation_redaction")
    payload["password"] = password
    captured_log = io.StringIO()
    handler = logging.StreamHandler(captured_log)
    logger = get_logger()
    attachments: dict[str, str] = {}
    original_attach = allure.attach

    def capture_attachment(body, name=None, attachment_type=None, extension=None):
        attachments[name] = body
        return original_attach(body, name=name, attachment_type=attachment_type, extension=extension)

    monkeypatch.setattr("common.http_client.allure.attach", capture_attachment)
    logger.addHandler(handler)
    try:
        response = test_data.register_user(auth_api, payload)
    finally:
        logger.removeHandler(handler)
        handler.close()

    assert response.status_code == 422
    raw = response.json()
    error = next(item for item in raw["detail"] if item["loc"][-1] == "password")
    assert error["type"] == expected_type
    # Prove the source contains the value; a negative-only check could pass vacuously.
    assert error["input"] == password
    sanitized = sanitize_data(raw)
    clean_error = next(item for item in sanitized["detail"] if item["loc"][-1] == "password")
    assert clean_error["input"] == "[REDACTED]"
    assert password not in json.dumps(sanitized)
    assert "HTTP Response" in captured_log.getvalue()
    assert "[REDACTED]" in captured_log.getvalue()
    assert password not in captured_log.getvalue()
    assert {"HTTP Request", "HTTP Response"} <= attachments.keys()
    assert all(password not in body for body in attachments.values())
    recorded = json.loads(attachments["HTTP Response"])["body"]
    recorded_error = next(item for item in recorded["detail"] if item["loc"][-1] == "password")
    assert recorded_error["input"] == "[REDACTED]"


@pytest.mark.auth
@pytest.mark.parametrize(
    "case_id",
    AUTH_LOGIN_CASES,
    ids=list(AUTH_LOGIN_CASES),
)
@allure.epic("接口自动化测试")
@allure.feature("异常与安全输入")
@allure.story("登录安全输入")
def test_login_treats_sql_injection_as_plain_input(
    auth_api: AuthApi,
    case_id: str,
) -> None:
    case = AUTH_LOGIN_CASES[case_id]
    allure.dynamic.title(f"{case_id} - {case['title']}")

    response = auth_api.login(case["request"])

    assert response.status_code == case["expected_status"]
    assert response.json() == {"detail": case["expected_detail"]}


@pytest.mark.product
@pytest.mark.parametrize(
    "case_id",
    PRODUCT_INVALID_CASES,
    ids=list(PRODUCT_INVALID_CASES),
)
@allure.epic("接口自动化测试")
@allure.feature("异常与安全输入")
@allure.story("商品参数校验")
def test_product_rejects_invalid_payload(
    product_api: ProductApi,
    test_data: TestDataManager,
    case_id: str,
) -> None:
    case = PRODUCT_INVALID_CASES[case_id]
    allure.dynamic.title(f"{case_id} - {case['title']}")
    payload = _resolve_payload(case["request"])

    response = test_data.create_product(product_api, payload)

    _assert_validation_error(response, case)


@pytest.mark.order
@pytest.mark.parametrize(
    "case_id",
    ORDER_INVALID_CASES,
    ids=list(ORDER_INVALID_CASES),
)
@allure.epic("接口自动化测试")
@allure.feature("异常与安全输入")
@allure.story("订单参数校验")
def test_order_rejects_invalid_payload(
    product_api: ProductApi,
    order_api: OrderApi,
    data_factory: DataFactory,
    test_data: TestDataManager,
    case_id: str,
) -> None:
    case = ORDER_INVALID_CASES[case_id]
    allure.dynamic.title(f"{case_id} - {case['title']}")
    product_response = test_data.create_product(
        product_api,
        data_factory.product_payload({"name": "Validation Product"}),
    )
    assert product_response.status_code == 201
    product_id = product_response.json()["id"]
    payload = _resolve_payload(case["request"], **{"$product_id": product_id})

    response = test_data.create_order(order_api, payload)

    _assert_validation_error(response, case)


@pytest.mark.auth
@pytest.mark.parametrize("resource", ("product", "order"))
@allure.epic("接口自动化测试")
@allure.feature("异常与安全输入")
@allure.story("无 Token 访问")
def test_missing_token_is_rejected_by_protected_resources(
    public_product_api: ProductApi,
    public_order_api: OrderApi,
    resource: str,
) -> None:
    if resource == "product":
        response = public_product_api.list_products()
    else:
        response = public_order_api.get_order(999999999)

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


@pytest.mark.auth
@pytest.mark.parametrize("resource", ("user", "product", "order"))
@allure.epic("接口自动化测试")
@allure.feature("异常与安全输入")
@allure.story("错误 Token 访问")
def test_invalid_token_is_rejected_by_protected_resources(
    authenticated_api_factory: AuthenticatedApiFactory,
    resource: str,
) -> None:
    with authenticated_api_factory("invalid-token") as (
        user_api,
        product_api,
        order_api,
    ):
        if resource == "user":
            response = user_api.get_current_user()
        elif resource == "product":
            response = product_api.list_products()
        else:
            response = order_api.get_order(999999999)

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired token"}


@pytest.mark.order
@allure.epic("接口自动化测试")
@allure.feature("异常与安全输入")
@allure.story("订单越权访问")
def test_order_is_not_accessible_to_another_user(
    auth_api: AuthApi,
    product_api: ProductApi,
    order_api: OrderApi,
    authenticated_api_factory: AuthenticatedApiFactory,
    data_factory: DataFactory,
    test_data: TestDataManager,
) -> None:
    product_response = test_data.create_product(
        product_api,
        data_factory.product_payload({"name": "Ownership Product"}),
    )
    assert product_response.status_code == 201
    order_response = test_data.create_order(
        order_api,
        data_factory.order_payload(product_response.json()["id"]),
    )
    assert order_response.status_code == 201
    order_id = order_response.json()["id"]

    other_user_payload = data_factory.user_payload("other_user")
    register_response = test_data.register_user(auth_api, other_user_payload)
    assert register_response.status_code == 201
    login_response = auth_api.login(
        {
            "username": other_user_payload["username"],
            "password": other_user_payload["password"],
        }
    )
    assert login_response.status_code == 200

    with authenticated_api_factory(login_response.json()["access_token"]) as (
        _other_user_api,
        _other_product_api,
        other_order_api,
    ):
        forbidden_responses = (
            other_order_api.get_order(order_id),
            other_order_api.pay_order(order_id),
            other_order_api.cancel_order(order_id),
        )

    for response in forbidden_responses:
        assert response.status_code == 404
        assert response.json() == {"detail": "Order not found"}

    owner_response = order_api.get_order(order_id)
    assert owner_response.status_code == 200
    assert owner_response.json()["status"] == "CREATED"


@pytest.mark.product
@pytest.mark.db
@allure.epic("接口自动化测试")
@allure.feature("异常与安全输入")
@allure.story("SQL Injection 输入")
def test_sql_injection_product_name_is_stored_as_plain_text(
    product_api: ProductApi,
    database_client: DatabaseClient,
    data_factory: DataFactory,
    test_data: TestDataManager,
) -> None:
    payload = data_factory.product_payload(
        {
            "name": "'; DROP TABLE products; --",
            "price": "10.00",
            "stock": 1,
            "status": "ACTIVE",
        }
    )

    response = test_data.create_product(product_api, payload)

    assert response.status_code == 201
    product_id = response.json()["id"]
    database_product = database_client.fetch_one(
        "SELECT name FROM products WHERE id = %s",
        (product_id,),
    )
    assert database_product == {"name": payload["name"]}
    list_response = product_api.list_products()
    assert list_response.status_code == 200
    assert product_id in {product["id"] for product in list_response.json()}
