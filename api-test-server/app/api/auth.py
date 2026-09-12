"""认证 HTTP 路由：把 Schema、Service 和 HTTP 语义连接起来。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_auth_settings, get_database_session
from app.core.config import AuthSettings
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserResponse
from app.services.auth_service import (
    InvalidCredentialsError,
    UserAlreadyExistsError,
    authenticate_user,
    register_user,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegisterRequest,
    session: Annotated[Session, Depends(get_database_session)],
) -> UserResponse:
    """注册用户；唯一键冲突返回 409，而不是底层数据库错误。"""

    try:
        user = register_user(
            session,
            username=payload.username,
            email=str(payload.email),
            password=payload.password,
        )
    except UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    session: Annotated[Session, Depends(get_database_session)],
    auth_settings: Annotated[AuthSettings, Depends(get_auth_settings)],
) -> TokenResponse:
    """验证凭据并签发 Bearer JWT。"""

    try:
        user = authenticate_user(
            session,
            username=payload.username,
            password=payload.password,
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # TokenResponse 不包含密码、哈希或其他用户敏感字段。
    return TokenResponse(
        access_token=create_access_token(user.id, auth_settings),
    )
