from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import delete, inspect, select
from sqlalchemy.orm import Session

from app.core.config import Settings
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


def test_database_creates_users_table_and_reads_data(
    database_settings: Settings,
) -> None:
    username = f"sprint9_{uuid4().hex}"
    email = f"{username}@example.com"

    with TestClient(create_app(database_settings)) as client:
        health_response = client.get("/health/db")
        engine = client.app.state.db_engine

        assert health_response.status_code == 200
        assert health_response.json() == {"status": "ok"}
        assert engine is not None
        assert inspect(engine).has_table("users")

        with Session(engine) as session:
            try:
                session.add(
                    User(
                        username=username,
                        email=email,
                        password_hash="sprint9-placeholder-hash",
                    )
                )
                session.commit()

                stored_user = session.scalar(
                    select(User).where(User.username == username)
                )

                assert stored_user is not None
                assert stored_user.email == email
                assert stored_user.is_active is True
            finally:
                session.rollback()
                session.execute(delete(User).where(User.username == username))
                session.commit()


def test_database_unavailable_returns_clear_error() -> None:
    unavailable_settings = Settings(
        db_host="127.0.0.1",
        db_port=1,
        db_user="unavailable",
        db_password="not-a-real-password",
        db_name="api_test",
    )

    with TestClient(create_app(unavailable_settings)) as client:
        response = client.get("/health/db")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}


def test_missing_database_configuration_returns_clear_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for variable_name in (
        "DB_HOST",
        "DB_PORT",
        "DB_USER",
        "DB_PASSWORD",
        "DB_NAME",
    ):
        monkeypatch.delenv(variable_name, raising=False)

    with TestClient(create_app()) as client:
        response = client.get("/health/db")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database configuration is invalid"}
