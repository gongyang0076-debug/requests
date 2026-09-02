from collections.abc import Generator
from decimal import Decimal
from typing import TypeAlias
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from app.core.config import AuthSettings, Settings
from app.main import create_app
from app.models import Product, User

AuthenticatedProductClient: TypeAlias = tuple[TestClient, dict[str, str], str]


@pytest.fixture
def authenticated_product_client(
    database_settings: Settings,
    auth_settings: AuthSettings,
) -> Generator[AuthenticatedProductClient, None, None]:
    suffix = uuid4().hex
    username = f"product_user_{suffix}"
    product_prefix = f"product_{suffix}"
    user_payload = {
        "username": username,
        "email": f"{username}@example.com",
        "password": f"ValidPassword_{suffix}",
    }

    with TestClient(create_app(database_settings, auth_settings)) as client:
        register_response = client.post("/api/auth/register", json=user_payload)
        assert register_response.status_code == 201
        login_response = client.post(
            "/api/auth/login",
            json={
                "username": username,
                "password": user_payload["password"],
            },
        )
        assert login_response.status_code == 200
        headers = {
            "Authorization": f"Bearer {login_response.json()['access_token']}"
        }
        engine: Engine = client.app.state.db_engine

        try:
            yield client, headers, product_prefix
        finally:
            with Session(engine) as session:
                session.execute(
                    delete(Product).where(Product.name.like(f"{product_prefix}%"))
                )
                session.execute(delete(User).where(User.username == username))
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
    database_settings: Settings,
    auth_settings: AuthSettings,
) -> None:
    with TestClient(create_app(database_settings, auth_settings)) as client:
        response = client.post(
            "/api/products",
            json={"name": "Unauthorized", "price": "10.00", "stock": 1},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
