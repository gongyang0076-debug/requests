from collections.abc import Generator
from typing import TypedDict

import pytest

from api.user_api import UserApi
from common.http_client import HttpClient


class FrameworkConfig(TypedDict):
    base_url: str
    timeout: float


@pytest.fixture(scope="session")
def config() -> FrameworkConfig:
    return {
        "base_url": "https://dummyjson.com",
        "timeout": 10.0,
    }


@pytest.fixture(scope="session")
def client(config: FrameworkConfig) -> Generator[HttpClient, None, None]:
    http_client = HttpClient(
        base_url=config["base_url"],
        timeout=config["timeout"],
    )
    yield http_client
    http_client.close()


@pytest.fixture
def user_api(client: HttpClient) -> UserApi:
    return UserApi(client)
