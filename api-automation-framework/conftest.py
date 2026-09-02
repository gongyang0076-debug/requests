from collections.abc import Generator
from typing import Any
from uuid import uuid4

import pytest

from api.auth_api import AuthApi
from api.user_api import UserApi
from common.http_client import HttpClient
from config.config import Settings, load_config


def pytest_addoption(parser: pytest.Parser) -> None:
    environment_group = parser.getgroup("environment")
    environment_group.addoption(
        "--env",
        action="store",
        choices=("test", "pre"),
        default=None,
        help="Environment from config/config.yaml (default: TEST_ENV or test)",
    )


@pytest.fixture(scope="session")
def config(pytestconfig: pytest.Config) -> Settings:
    return load_config(pytestconfig.getoption("--env"))


@pytest.fixture(scope="session")
def client(config: Settings) -> Generator[HttpClient, None, None]:
    http_client = HttpClient(
        base_url=config.base_url,
        timeout=config.timeout,
    )
    yield http_client
    http_client.close()


@pytest.fixture(scope="session")
def auth_api(client: HttpClient) -> AuthApi:
    return AuthApi(client)


@pytest.fixture(scope="session")
def registered_user(auth_api: AuthApi) -> dict[str, Any]:
    suffix = uuid4().hex
    payload = {
        "username": f"api_auto_{suffix}",
        "email": f"api_auto_{suffix}@example.com",
        "password": f"AutomationPassword_{suffix}",
    }
    response = auth_api.register(payload)

    assert response.status_code == 201, (
        f"Registration setup failed: status={response.status_code}, "
        f"response={response.text}"
    )

    response_body = response.json()
    return {
        **payload,
        "id": response_body["id"],
        "is_active": response_body["is_active"],
    }


@pytest.fixture(scope="session")
def auth_token(auth_api: AuthApi, registered_user: dict[str, Any]) -> str:
    response = auth_api.login(
        {
            "username": registered_user["username"],
            "password": registered_user["password"],
        }
    )

    assert response.status_code == 200, (
        f"Login setup failed: status={response.status_code}, "
        f"response={response.text}"
    )

    response_body = response.json()
    assert response_body["token_type"] == "bearer"
    assert response_body["access_token"]
    return response_body["access_token"]


@pytest.fixture(scope="session")
def auth_client(
    config: Settings,
    auth_token: str,
) -> Generator[HttpClient, None, None]:
    http_client = HttpClient(
        base_url=config.base_url,
        timeout=config.timeout,
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    yield http_client
    http_client.close()


@pytest.fixture
def user_api(auth_client: HttpClient) -> UserApi:
    return UserApi(auth_client)


@pytest.fixture
def public_user_api(client: HttpClient) -> UserApi:
    return UserApi(client)
