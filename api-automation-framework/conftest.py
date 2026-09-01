from collections.abc import Generator

import pytest

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


@pytest.fixture
def user_api(client: HttpClient) -> UserApi:
    return UserApi(client)
