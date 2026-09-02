from collections.abc import Generator
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import Engine, delete
from sqlalchemy.orm import Session

from app.core.config import AuthSettings, Settings
from app.main import create_app
from app.models import User


@pytest.fixture(scope="session")
def database_settings() -> Settings:
    try:
        settings = Settings()
    except ValidationError:
        pytest.fail(
            "Real MySQL integration tests require DB_HOST, DB_PORT, DB_USER, "
            "DB_PASSWORD and DB_NAME"
        )

    if settings.db_name != "api_test":
        pytest.fail("Database integration tests must use the isolated api_test database")

    return settings


@pytest.fixture(scope="session")
def auth_settings() -> AuthSettings:
    try:
        return AuthSettings()
    except ValidationError:
        pytest.fail(
            "Authentication tests require JWT_SECRET_KEY with at least 32 characters"
        )


@pytest.fixture
def authenticated_client(
    database_settings: Settings,
    auth_settings: AuthSettings,
) -> Generator[dict[str, Any], None, None]:
    suffix = uuid4().hex
    username = f"test_user_{suffix}"
    password = f"ValidPassword_{suffix}"

    with TestClient(create_app(database_settings, auth_settings)) as client:
        register_response = client.post(
            "/api/auth/register",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password": password,
            },
        )
        assert register_response.status_code == 201
        user_id = register_response.json()["id"]

        login_response = client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
        )
        assert login_response.status_code == 200
        context = {
            "client": client,
            "headers": {
                "Authorization": f"Bearer {login_response.json()['access_token']}"
            },
            "engine": client.app.state.db_engine,
            "suffix": suffix,
            "user_id": user_id,
            "username": username,
        }

        try:
            yield context
        finally:
            engine: Engine = context["engine"]
            with Session(engine) as session:
                session.execute(delete(User).where(User.id == user_id))
                session.commit()
