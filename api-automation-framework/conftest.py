"""Pytest 全局 Fixture 层。

本文件管理测试运行所需的依赖和生命周期，包括：
- 命令行选项 --env：选择测试环境
- 配置对象（Settings / DatabaseSettings）
- HttpClient：公共 Client（未登录）和认证 Client（已带 Bearer Token）
- API Object：UserApi / ProductApi / OrderApi / AuthApi / HealthApi
- 数据库客户端：用于 DB 断言和 Teardown 清理
- 动态用户 / JWT：会话级共享一个已注册用户和它的 Token
- TestDataManager：用例级资源登记与清理

Scope 策略：
    session scope —— 共享且无状态的资源（配置、Client、数据库连接、登录态）
    function scope —— 每条用例独立、用完即清理的资源（test_data 等）
"""

from collections.abc import Callable, Generator, Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Any

import pytest

from api.auth_api import AuthApi
from api.health_api import HealthApi
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

# 认证后的 API 三件套：UserApi / ProductApi / OrderApi
AuthenticatedApiSet = tuple[UserApi, ProductApi, OrderApi]
# 认证 API 工厂类型：传入 token，返回一个上下文管理器，yield 出 API 三件套
AuthenticatedApiFactory = Callable[
    [str],
    AbstractContextManager[AuthenticatedApiSet],
]


def pytest_addoption(parser: pytest.Parser) -> None:
    """注册命令行选项 --env，用于选择 config.yaml 中的环境。

    用法：python -m pytest --env=test
    不传时回退到 TEST_ENV 环境变量或默认 "test"。
    """
    environment_group = parser.getgroup("environment")
    environment_group.addoption(
        "--env",
        action="store",
        choices=("test", "pre"),  # 只允许这两个值
        default=None,
        help="Environment from config/config.yaml (default: TEST_ENV or test)",
    )


@pytest.fixture(scope="session")
def config(pytestconfig: pytest.Config) -> Settings:
    """会话级：加载 API 测试配置（base_url / timeout）。

    只加载一次，整个测试会话共享，避免重复读 YAML。
    """
    return load_config(pytestconfig.getoption("--env"))


@pytest.fixture(scope="session")
def database_config() -> DatabaseSettings:
    """会话级：加载 MySQL 连接配置（来自 .env / 环境变量）。"""
    return load_database_config()


@pytest.fixture(scope="session")
def database_client(
    database_config: DatabaseSettings,
) -> Generator[DatabaseClient, None, None]:
    """会话级：建立到 MySQL 的连接，用例结束后关闭。

    用于 DB 断言（如支付后查 orders.status）和 Teardown 数据清理。
    """
    mysql_client = DatabaseClient(database_config)
    yield mysql_client
    # 会话结束时关闭连接
    mysql_client.close()


@pytest.fixture(scope="session")
def data_factory() -> DataFactory:
    """会话级：Faker 数据工厂，生成唯一用户名/商品名等动态数据。"""
    return DataFactory()


@pytest.fixture(scope="session")
def client(config: Settings) -> Generator[HttpClient, None, None]:
    """会话级：公共 HttpClient（未登录）。

    基础连接池和 headers 在整个会话复用；健康检查、注册、登录等
    不需要鉴权的接口用它。
    """
    http_client = HttpClient(
        base_url=config.base_url,
        timeout=config.timeout,
    )
    yield http_client
    http_client.close()


@pytest.fixture(scope="session")
def auth_api(client: HttpClient) -> AuthApi:
    """会话级：认证 API 对象，基于公共 Client（注册/登录本身不需要登录态）。"""
    return AuthApi(client)


@pytest.fixture(scope="session")
def health_api(client: HttpClient) -> HealthApi:
    """会话级：健康检查 API 对象，基于公共 Client。"""
    return HealthApi(client)


@pytest.fixture(scope="session")
def registered_user(
    auth_api: AuthApi,
    data_factory: DataFactory,
    database_client: DatabaseClient,
) -> Generator[dict[str, Any], None, None]:
    """会话级：注册一个用户并在会话结束时清理。

    返回包含 username/email/password/id/is_active 的字典，
    供 auth_token / 等其他 fixture 复用。会话结束直接用 SQL 删除该用户。
    """
    payload = data_factory.user_payload()
    response = auth_api.register(payload)

    # 注册必须成功，否则后续依赖它的用例都无意义
    assert response.status_code == 201, (
        f"Registration setup failed: status={response.status_code}, "
        f"response={response.text}"
    )

    response_body = response.json()
    # 把请求 payload 和响应中的 id / is_active 合并，便于后续直接使用
    user = {
        **payload,
        "id": response_body["id"],
        "is_active": response_body["is_active"],
    }
    yield user
    # Teardown：直接删用户
    database_client.execute(
        "DELETE FROM users WHERE id = %s",
        (user["id"],),
    )


@pytest.fixture(scope="session")
def auth_token(auth_api: AuthApi, registered_user: dict[str, Any]) -> str:
    """会话级：用已注册用户登录，返回 JWT access_token。

    整个会话共用一个 Token；如需独立登录态可用 authenticated_api_factory。
    """
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
    # 校验返回的是 bearer 类型 token，且非空
    assert response_body["token_type"] == "bearer"
    assert response_body["access_token"]
    return response_body["access_token"]


@pytest.fixture(scope="session")
def auth_client(
    config: Settings,
    auth_token: str,
) -> Generator[HttpClient, None, None]:
    """会话级：认证 HttpClient，Session Header 已注入 Bearer Token。

    所有需要登录态的 API Object 都基于它，测试不用每次手动传 Token。
    """
    http_client = HttpClient(
        base_url=config.base_url,
        timeout=config.timeout,
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    yield http_client
    http_client.close()


# ---- 以下为 function scope：每条用例独立获取新的 API Object ----
# 因为 API Object 本身无状态（只是持有 Client 引用），function scope 也只是
# 给每条用例一个独立的包装，但底层 Client / 登录态仍是会话级共享的。


@pytest.fixture
def user_api(auth_client: HttpClient) -> UserApi:
    """用例级：已认证的 UserApi（GET /api/users/me）。"""
    return UserApi(auth_client)


@pytest.fixture
def public_user_api(client: HttpClient) -> UserApi:
    """用例级：未认证的 UserApi，用于测试无 Token / 错误 Token 的鉴权场景。"""
    return UserApi(client)


@pytest.fixture
def public_product_api(client: HttpClient) -> ProductApi:
    """用例级：未认证的 ProductApi，用于测试未登录访问受保护接口的拒绝场景。"""
    return ProductApi(client)


@pytest.fixture
def public_order_api(client: HttpClient) -> OrderApi:
    """用例级：未认证的 OrderApi，用于测试未登录访问订单接口的拒绝场景。"""
    return OrderApi(client)


@pytest.fixture
def product_api(auth_client: HttpClient) -> ProductApi:
    """用例级：已认证的 ProductApi。"""
    return ProductApi(auth_client)


@pytest.fixture
def order_api(auth_client: HttpClient) -> OrderApi:
    """用例级：已认证的 OrderApi。"""
    return OrderApi(auth_client)


@pytest.fixture
def test_data(
    database_client: DatabaseClient,
    product_api: ProductApi,
) -> Generator[TestDataManager, None, None]:
    """用例级：测试数据管理器。

    用例中通过它注册用户、创建商品、创建订单，ID 自动登记；
    用例结束时调用 cleanup() 按 Order → Product → User 顺序清理，
    保证每条用例独立、可重复运行。
    """
    manager = TestDataManager(
        database_client=database_client,
        cleanup_product_api=product_api,
    )
    yield manager
    # Teardown：清理本用例创建的所有资源
    manager.cleanup()


@pytest.fixture
def authenticated_api_factory(config: Settings) -> AuthenticatedApiFactory:
    """用例级：认证 API 工厂。

    用于需要"独立登录态"的用例（如并发测试、不同用户视角）：
        def test_x(authenticated_api_factory):
            with authenticated_api_factory(token) as (user_api, product_api, order_api):
                ...

    每次调用都会新建一个 HttpClient 并在退出时自动关闭，登录态互不干扰。
    """
    @contextmanager
    def build(token: str) -> Iterator[AuthenticatedApiSet]:
        # 用传入的 token 构造一个独立的认证 Client
        http_client = HttpClient(
            base_url=config.base_url,
            timeout=config.timeout,
            headers={"Authorization": f"Bearer {token}"},
        )
        try:
            # 返回认证后的 API 三件套
            yield (
                UserApi(http_client),
                ProductApi(http_client),
                OrderApi(http_client),
            )
        finally:
            # 退出 with 块时关闭 Client，释放连接
            http_client.close()

    return build
