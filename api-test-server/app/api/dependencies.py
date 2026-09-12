"""FastAPI 路由共享依赖。

这里集中管理请求级数据库 Session、JWT 配置和当前登录用户。业务路由只声明
需要的依赖，不重复编写 Token 解析或数据库可用性判断。
"""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.config import AuthSettings
from app.core.security import InvalidAccessTokenError, decode_access_token
from app.models import User

# 关闭 FastAPI 默认错误，统一由 get_current_user 返回项目约定的 401 响应。
BEARER_SCHEME = HTTPBearer(auto_error=False)


def get_database_session(request: Request) -> Iterator[Session]:
    """为单个请求创建 Session，并在请求结束后自动关闭。"""

    engine: Engine | None = request.app.state.db_engine
    if engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=request.app.state.database_error,
        )

    # Session 是请求级工作单元；commit 由 Service 在业务成功后明确执行。
    with Session(engine) as session:
        yield session


def get_auth_settings(request: Request) -> AuthSettings:
    """取得启动阶段已验证过的 JWT 配置。"""

    auth_settings: AuthSettings | None = request.app.state.auth_settings
    if auth_settings is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=request.app.state.auth_error,
        )
    return auth_settings


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(BEARER_SCHEME),
    ],
    session: Annotated[Session, Depends(get_database_session)],
    auth_settings: Annotated[AuthSettings, Depends(get_auth_settings)],
) -> User:
    """验证 Bearer Token 并返回仍处于激活状态的数据库用户。"""

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # decode_access_token 同时校验签名、算法、exp 与 sub 声明。
        user_id = decode_access_token(credentials.credentials, auth_settings)
    except InvalidAccessTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # Token 有效还不够：用户被删除或停用后也不能继续访问受保护资源。
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
