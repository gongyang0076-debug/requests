"""FastAPI 应用装配入口。

应用启动时创建数据库 Engine、初始化当前模型的表并把运行时依赖放入
``app.state``；路由层再通过 Depends 取得这些依赖。这样测试可以向
``create_app`` 注入独立配置，而不是依赖模块级全局状态。
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, ValidationError
from sqlalchemy import Engine

from app.api.auth import router as auth_router
from app.api.orders import router as orders_router
from app.api.products import router as products_router
from app.api.users import router as users_router
from app.core.config import AuthSettings, Settings
from app.database.session import (
    DatabaseUnavailableError,
    create_database_engine,
    initialize_database,
    verify_database_connection,
)


class HealthResponse(BaseModel):
    """两个健康检查接口共用的最小响应结构。"""

    status: Literal["ok"]


def create_app(
    settings: Settings | None = None,
    auth_settings: AuthSettings | None = None,
) -> FastAPI:
    """创建可运行的 FastAPI 应用。

    可选参数主要服务于测试：传入后会覆盖从本地环境加载的配置，使不同
    测试可使用自己的 MySQL 和 JWT 设置。
    """

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        # 生命周期负责基础设施的创建与释放；请求处理阶段不再重复创建 Engine。
        engine: Engine | None = None
        database_error: str | None = None
        resolved_auth_settings: AuthSettings | None = None
        auth_error: str | None = None

        try:
            database_settings = settings or Settings()
            engine = create_database_engine(database_settings)
            # create_all 仅创建当前缺失的表，方便隔离测试库从空状态启动。
            initialize_database(engine)
        except ValidationError:
            database_error = "Database configuration is invalid"
        except DatabaseUnavailableError:
            database_error = "Database unavailable"
            if engine is not None:
                engine.dispose()
            engine = None

        try:
            resolved_auth_settings = auth_settings or AuthSettings()
        except ValidationError:
            auth_error = "Authentication configuration is invalid"

        application.state.db_engine = engine
        application.state.database_error = database_error
        application.state.auth_settings = resolved_auth_settings
        application.state.auth_error = auth_error

        try:
            # 应用开始接收请求。路由依赖会从 application.state 获取上述对象。
            yield
        finally:
            # 无论启动后的请求是否失败，都释放连接池，避免测试之间残留连接。
            if engine is not None:
                engine.dispose()

    application = FastAPI(
        title="API Test Server",
        description="Controllable backend for the API automation framework.",
        version="0.5.0",
        lifespan=lifespan,
    )
    application.include_router(auth_router)
    application.include_router(users_router)
    application.include_router(products_router)
    application.include_router(orders_router)

    @application.get("/health", response_model=HealthResponse)
    async def get_health() -> HealthResponse:
        # 只说明 Web 应用进程存活，不保证 MySQL 可用。
        return HealthResponse(status="ok")

    @application.get("/health/db", response_model=HealthResponse)
    def get_database_health(request: Request) -> HealthResponse:
        # /health/db 是自动化框架和 CI 启动服务后的就绪检查。
        engine: Engine | None = request.app.state.db_engine
        if engine is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=request.app.state.database_error,
            )

        try:
            # 真正执行 SELECT 1，避免仅凭 Engine 对象存在就误判数据库可用。
            verify_database_connection(engine)
        except DatabaseUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database unavailable",
            ) from exc

        return HealthResponse(status="ok")

    return application


app = create_app()
