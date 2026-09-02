from collections.abc import Generator
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session

from app.models import Order, Product


@pytest.fixture
def order_test_context(
    authenticated_client: dict[str, Any],
) -> Generator[dict[str, Any], None, None]:
    client: TestClient = authenticated_client["client"]
    headers: dict[str, str] = authenticated_client["headers"]
    engine: Engine = authenticated_client["engine"]
    product_response = client.post(
        "/api/products",
        json={
            "name": f"order_product_{authenticated_client['suffix']}",
            "price": "12.50",
            "stock": 5,
            "status": "ACTIVE",
        },
        headers=headers,
    )
    assert product_response.status_code == 201
    product_id = product_response.json()["id"]
    context = {
        **authenticated_client,
        "product_id": product_id,
    }

    try:
        yield context
    finally:
        with Session(engine) as session:
            session.execute(
                delete(Order).where(Order.user_id == authenticated_client["user_id"])
            )
            session.execute(delete(Product).where(Product.id == product_id))
            session.commit()


def _create_order(
    context: dict[str, Any],
    *,
    quantity: int = 1,
) -> dict[str, Any]:
    client: TestClient = context["client"]
    response = client.post(
        "/api/orders",
        json={"product_id": context["product_id"], "quantity": quantity},
        headers=context["headers"],
    )
    assert response.status_code == 201
    return response.json()


def test_create_and_get_order_persists_total_and_reduces_stock(
    order_test_context: dict[str, Any],
) -> None:
    client: TestClient = order_test_context["client"]
    order = _create_order(order_test_context, quantity=2)

    assert order["user_id"] == order_test_context["user_id"]
    assert order["product_id"] == order_test_context["product_id"]
    assert order["quantity"] == 2
    assert Decimal(order["total_amount"]) == Decimal("25.00")
    assert order["status"] == "CREATED"
    assert order["created_at"]

    engine: Engine = order_test_context["engine"]
    with Session(engine) as session:
        stored_order = session.get(Order, order["id"])
        stored_product = session.get(Product, order_test_context["product_id"])
        assert stored_order is not None
        assert stored_order.total_amount == Decimal("25.00")
        assert stored_order.status == "CREATED"
        assert stored_product is not None
        assert stored_product.stock == 3

    response = client.get(
        f"/api/orders/{order['id']}",
        headers=order_test_context["headers"],
    )
    assert response.status_code == 200
    assert response.json()["id"] == order["id"]
    assert response.json()["status"] == "CREATED"


def test_pay_order_and_reject_repeated_payment_or_cancellation(
    order_test_context: dict[str, Any],
) -> None:
    client: TestClient = order_test_context["client"]
    order = _create_order(order_test_context)

    pay_response = client.post(
        f"/api/orders/{order['id']}/pay",
        headers=order_test_context["headers"],
    )
    assert pay_response.status_code == 200
    assert pay_response.json()["status"] == "PAID"

    get_response = client.get(
        f"/api/orders/{order['id']}",
        headers=order_test_context["headers"],
    )
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "PAID"

    repeated_pay_response = client.post(
        f"/api/orders/{order['id']}/pay",
        headers=order_test_context["headers"],
    )
    assert repeated_pay_response.status_code == 409
    assert repeated_pay_response.json() == {
        "detail": "Order cannot be paid when status is PAID"
    }

    cancel_response = client.post(
        f"/api/orders/{order['id']}/cancel",
        headers=order_test_context["headers"],
    )
    assert cancel_response.status_code == 409
    assert cancel_response.json() == {
        "detail": "Order cannot be cancelled when status is PAID"
    }


def test_cancel_order_restores_stock_and_rejects_later_transitions(
    order_test_context: dict[str, Any],
) -> None:
    client: TestClient = order_test_context["client"]
    order = _create_order(order_test_context, quantity=2)

    cancel_response = client.post(
        f"/api/orders/{order['id']}/cancel",
        headers=order_test_context["headers"],
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "CANCELLED"

    product_response = client.get(
        f"/api/products/{order_test_context['product_id']}",
        headers=order_test_context["headers"],
    )
    assert product_response.status_code == 200
    assert product_response.json()["stock"] == 5

    pay_response = client.post(
        f"/api/orders/{order['id']}/pay",
        headers=order_test_context["headers"],
    )
    assert pay_response.status_code == 409
    assert pay_response.json() == {
        "detail": "Order cannot be paid when status is CANCELLED"
    }

    repeated_cancel_response = client.post(
        f"/api/orders/{order['id']}/cancel",
        headers=order_test_context["headers"],
    )
    assert repeated_cancel_response.status_code == 409


def test_create_order_rejects_insufficient_stock_without_creating_order(
    order_test_context: dict[str, Any],
) -> None:
    client: TestClient = order_test_context["client"]
    update_response = client.put(
        f"/api/products/{order_test_context['product_id']}",
        json={
            "name": f"low_stock_{order_test_context['suffix']}",
            "price": "12.50",
            "stock": 1,
            "status": "ACTIVE",
        },
        headers=order_test_context["headers"],
    )
    assert update_response.status_code == 200

    response = client.post(
        "/api/orders",
        json={"product_id": order_test_context["product_id"], "quantity": 2},
        headers=order_test_context["headers"],
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "Insufficient stock"}

    engine: Engine = order_test_context["engine"]
    with Session(engine) as session:
        order_count = session.scalar(
            select(func.count()).select_from(Order).where(
                Order.product_id == order_test_context["product_id"]
            )
        )
        product = session.get(Product, order_test_context["product_id"])
        assert order_count == 0
        assert product is not None
        assert product.stock == 1


def test_create_order_rejects_missing_product(
    authenticated_client: dict[str, Any],
) -> None:
    client: TestClient = authenticated_client["client"]
    response = client.post(
        "/api/orders",
        json={"product_id": 999999999, "quantity": 1},
        headers=authenticated_client["headers"],
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Product not found"}


@pytest.mark.parametrize("quantity", [0, -1])
def test_create_order_rejects_invalid_quantity(
    order_test_context: dict[str, Any],
    quantity: int,
) -> None:
    client: TestClient = order_test_context["client"]
    response = client.post(
        "/api/orders",
        json={
            "product_id": order_test_context["product_id"],
            "quantity": quantity,
        },
        headers=order_test_context["headers"],
    )

    assert response.status_code == 422


@pytest.mark.parametrize("operation", ["get", "pay", "cancel"])
def test_order_operations_return_404_for_missing_order(
    authenticated_client: dict[str, Any],
    operation: str,
) -> None:
    client: TestClient = authenticated_client["client"]
    suffix = "" if operation == "get" else f"/{operation}"
    method = "GET" if operation == "get" else "POST"
    response = client.request(
        method,
        f"/api/orders/999999999{suffix}",
        headers=authenticated_client["headers"],
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Order not found"}


def test_create_order_requires_token(
    order_test_context: dict[str, Any],
) -> None:
    client: TestClient = order_test_context["client"]
    response = client.post(
        "/api/orders",
        json={"product_id": order_test_context["product_id"], "quantity": 1},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_create_order_rejects_inactive_product(
    order_test_context: dict[str, Any],
) -> None:
    client: TestClient = order_test_context["client"]
    update_response = client.put(
        f"/api/products/{order_test_context['product_id']}",
        json={
            "name": f"inactive_{order_test_context['suffix']}",
            "price": "12.50",
            "stock": 5,
            "status": "INACTIVE",
        },
        headers=order_test_context["headers"],
    )
    assert update_response.status_code == 200

    response = client.post(
        "/api/orders",
        json={"product_id": order_test_context["product_id"], "quantity": 1},
        headers=order_test_context["headers"],
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Product is inactive"}
