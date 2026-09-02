from collections.abc import Generator
from decimal import Decimal
from typing import Any, TypeAlias

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from app.models import Product

AuthenticatedProductClient: TypeAlias = tuple[TestClient, dict[str, str], str]


@pytest.fixture
def authenticated_product_client(
    authenticated_client: dict[str, Any],
) -> Generator[AuthenticatedProductClient, None, None]:
    client: TestClient = authenticated_client["client"]
    headers: dict[str, str] = authenticated_client["headers"]
    engine: Engine = authenticated_client["engine"]
    product_prefix = f"product_{authenticated_client['suffix']}"

    try:
        yield client, headers, product_prefix
    finally:
        with Session(engine) as session:
            session.execute(
                delete(Product).where(Product.name.like(f"{product_prefix}%"))
            )
            session.commit()


def test_product_crud_and_database_persistence(
    authenticated_product_client: AuthenticatedProductClient,
) -> None:
    client, headers, product_prefix = authenticated_product_client
    create_payload = {
        "name": f"{product_prefix}_original",
        "price": "19.99",
        "stock": 10,
        "status": "ACTIVE",
    }

    create_response = client.post(
        "/api/products",
        json=create_payload,
        headers=headers,
    )

    assert create_response.status_code == 201
    created = create_response.json()
    product_id = created["id"]
    assert created["name"] == create_payload["name"]
    assert Decimal(created["price"]) == Decimal("19.99")
    assert created["stock"] == 10
    assert created["status"] == "ACTIVE"
    assert created["created_at"]

    engine: Engine = client.app.state.db_engine
    with Session(engine) as session:
        stored_product = session.scalar(
            select(Product).where(Product.id == product_id)
        )
        assert stored_product is not None
        assert stored_product.price == Decimal("19.99")
        assert stored_product.stock == 10

    get_response = client.get(f"/api/products/{product_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["id"] == product_id

    list_response = client.get("/api/products", headers=headers)
    assert list_response.status_code == 200
    assert product_id in {product["id"] for product in list_response.json()}

    update_payload = {
        "name": f"{product_prefix}_updated",
        "price": "25.50",
        "stock": 0,
        "status": "INACTIVE",
    }
    update_response = client.put(
        f"/api/products/{product_id}",
        json=update_payload,
        headers=headers,
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["name"] == update_payload["name"]
    assert Decimal(updated["price"]) == Decimal("25.50")
    assert updated["stock"] == 0
    assert updated["status"] == "INACTIVE"

    delete_response = client.delete(f"/api/products/{product_id}", headers=headers)
    assert delete_response.status_code == 204
    assert delete_response.content == b""

    missing_response = client.get(f"/api/products/{product_id}", headers=headers)
    assert missing_response.status_code == 404
    assert missing_response.json() == {"detail": "Product not found"}


@pytest.mark.parametrize("price", ["0", "-0.01"])
def test_create_product_rejects_invalid_price(
    authenticated_product_client: AuthenticatedProductClient,
    price: str,
) -> None:
    client, headers, product_prefix = authenticated_product_client
    response = client.post(
        "/api/products",
        json={
            "name": f"{product_prefix}_invalid_price",
            "price": price,
            "stock": 1,
        },
        headers=headers,
    )

    assert response.status_code == 422


def test_create_product_rejects_negative_stock(
    authenticated_product_client: AuthenticatedProductClient,
) -> None:
    client, headers, product_prefix = authenticated_product_client
    response = client.post(
        "/api/products",
        json={
            "name": f"{product_prefix}_invalid_stock",
            "price": "10.00",
            "stock": -1,
        },
        headers=headers,
    )

    assert response.status_code == 422


def test_create_product_rejects_xss_markup(
    authenticated_product_client: AuthenticatedProductClient,
) -> None:
    client, headers, _product_prefix = authenticated_product_client
    response = client.post(
        "/api/products",
        json={
            "name": "<script>alert('xss')</script>",
            "price": "10.00",
            "stock": 1,
        },
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "name"


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
def test_product_operations_return_404_for_missing_product(
    authenticated_product_client: AuthenticatedProductClient,
    method: str,
) -> None:
    client, headers, product_prefix = authenticated_product_client
    payload = {
        "name": f"{product_prefix}_missing",
        "price": "10.00",
        "stock": 1,
        "status": "ACTIVE",
    }
    response = client.request(
        method,
        "/api/products/999999999",
        json=payload if method == "PUT" else None,
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Product not found"}


def test_create_product_requires_token(
    authenticated_client: dict[str, Any],
) -> None:
    client: TestClient = authenticated_client["client"]
    response = client.post(
        "/api/products",
        json={"name": "Unauthorized", "price": "10.00", "stock": 1},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
