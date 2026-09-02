import pytest
from pydantic import ValidationError

from app.core.config import AuthSettings, Settings


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
