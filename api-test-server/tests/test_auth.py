from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from app.core.config import AuthSettings, Settings
from app.core.security import verify_password
from app.main import create_app
from app.models import User


def _user_payload() -> dict[str, str]:
    suffix = uuid4().hex
    return {
        "username": f"user_{suffix}",
        "email": f"user_{suffix}@example.com",
        "password": f"ValidPassword_{suffix}",
    }


def _delete_user(engine: Engine, username: str) -> None:
    with Session(engine) as session:
        session.execute(delete(User).where(User.username == username))
        session.commit()


def test_register_login_and_get_current_user(
    database_settings: Settings,
    auth_settings: AuthSettings,
) -> None:
    payload = _user_payload()

    with TestClient(create_app(database_settings, auth_settings)) as client:
        engine = client.app.state.db_engine
        try:
            register_response = client.post("/api/auth/register", json=payload)

            assert register_response.status_code == 201
            registered_user = register_response.json()
            assert registered_user["username"] == payload["username"]
            assert registered_user["email"] == payload["email"]
            assert "password" not in registered_user
            assert "password_hash" not in registered_user

            with Session(engine) as session:
                stored_user = session.scalar(
                    select(User).where(User.username == payload["username"])
                )
                assert stored_user is not None
                assert stored_user.password_hash != payload["password"]
                assert verify_password(
                    payload["password"],
                    stored_user.password_hash,
                )

            login_response = client.post(
                "/api/auth/login",
                json={
                    "username": payload["username"],
                    "password": payload["password"],
                },
            )

            assert login_response.status_code == 200
            token_body = login_response.json()
            assert token_body["token_type"] == "bearer"
            assert token_body["access_token"]

            current_user_response = client.get(
                "/api/users/me",
                headers={
                    "Authorization": f"Bearer {token_body['access_token']}"
                },
            )

            assert current_user_response.status_code == 200
            assert current_user_response.json()["id"] == registered_user["id"]
            assert current_user_response.json()["username"] == payload["username"]
        finally:
            _delete_user(engine, payload["username"])


def test_login_with_wrong_password_returns_401(
    database_settings: Settings,
    auth_settings: AuthSettings,
) -> None:
    payload = _user_payload()

    with TestClient(create_app(database_settings, auth_settings)) as client:
        engine = client.app.state.db_engine
        try:
            register_response = client.post("/api/auth/register", json=payload)
            assert register_response.status_code == 201

            response = client.post(
                "/api/auth/login",
                json={
                    "username": payload["username"],
                    "password": "WrongPassword_123",
                },
            )

            assert response.status_code == 401
            assert response.json() == {"detail": "Invalid username or password"}
        finally:
            _delete_user(engine, payload["username"])


@pytest.mark.parametrize("authorization", [None, "Bearer invalid-token"])
def test_get_current_user_rejects_missing_or_invalid_token(
    database_settings: Settings,
    auth_settings: AuthSettings,
    authorization: str | None,
) -> None:
    headers = {"Authorization": authorization} if authorization else {}

    with TestClient(create_app(database_settings, auth_settings)) as client:
        response = client.get("/api/users/me", headers=headers)

    assert response.status_code == 401


def test_login_sql_injection_is_treated_as_plain_input(
    database_settings: Settings,
    auth_settings: AuthSettings,
) -> None:
    with TestClient(create_app(database_settings, auth_settings)) as client:
        response = client.post(
            "/api/auth/login",
            json={
                "username": "' OR '1'='1' --",
                "password": "irrelevant",
            },
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid username or password"}


def test_login_returns_503_when_auth_configuration_is_missing(
    database_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for variable_name in (
        "JWT_SECRET_KEY",
        "JWT_ALGORITHM",
        "ACCESS_TOKEN_EXPIRE_MINUTES",
    ):
        monkeypatch.delenv(variable_name, raising=False)

    with TestClient(create_app(database_settings)) as client:
        response = client.post(
            "/api/auth/login",
            json={"username": "nobody", "password": "irrelevant"},
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Authentication configuration is invalid"
    }
