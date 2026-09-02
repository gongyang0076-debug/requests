from collections.abc import Callable, Generator, Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Any

import pytest

from api.auth_api import AuthApi
from api.order_api import OrderApi
from api.product_api import ProductApi
from api.user_api import UserApi
from common.database import DatabaseClient
from common.http_client import HttpClient
from config.config import (
    DatabaseSettings,
    Settings,
    load_config,
    load_database_config,
)
from utils.data_factory import DataFactory
from utils.data_lifecycle import TestDataManager

AuthenticatedApiSet = tuple[UserApi, ProductApi, OrderApi]
AuthenticatedApiFactory = Callable[
    [str],
    AbstractContextManager[AuthenticatedApiSet],
]


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
def database_config() -> DatabaseSettings:
    return load_database_config()


@pytest.fixture(scope="session")
def database_client(
    database_config: DatabaseSettings,
) -> Generator[DatabaseClient, None, None]:
    mysql_client = DatabaseClient(database_config)
    yield mysql_client
    mysql_client.close()


@pytest.fixture(scope="session")
def data_factory() -> DataFactory:
    return DataFactory()


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
def registered_user(
    auth_api: AuthApi,
    data_factory: DataFactory,
    database_client: DatabaseClient,
) -> Generator[dict[str, Any], None, None]:
    payload = data_factory.user_payload()
    response = auth_api.register(payload)

    assert response.status_code == 201, (
        f"Registration setup failed: status={response.status_code}, "
        f"response={response.text}"
    )

    response_body = response.json()
    user = {
        **payload,
        "id": response_body["id"],
        "is_active": response_body["is_active"],
    }
    yield user
    database_client.execute(
        "DELETE FROM users WHERE id = %s",
        (user["id"],),
    )


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


@pytest.fixture
def public_product_api(client: HttpClient) -> ProductApi:
    return ProductApi(client)


@pytest.fixture
def public_order_api(client: HttpClient) -> OrderApi:
    return OrderApi(client)


@pytest.fixture
def product_api(auth_client: HttpClient) -> ProductApi:
    return ProductApi(auth_client)


@pytest.fixture
def order_api(auth_client: HttpClient) -> OrderApi:
    return OrderApi(auth_client)


@pytest.fixture
def test_data(
    database_client: DatabaseClient,
    product_api: ProductApi,
) -> Generator[TestDataManager, None, None]:
    manager = TestDataManager(
        database_client=database_client,
        cleanup_product_api=product_api,
    )
    yield manager
    manager.cleanup()


@pytest.fixture
def authenticated_api_factory(config: Settings) -> AuthenticatedApiFactory:
    @contextmanager
    def build(token: str) -> Iterator[AuthenticatedApiSet]:
        http_client = HttpClient(
            base_url=config.base_url,
            timeout=config.timeout,
            headers={"Authorization": f"Bearer {token}"},
        )
        try:
            yield (
                UserApi(http_client),
                ProductApi(http_client),
                OrderApi(http_client),
            )
        finally:
            http_client.close()

    return build
