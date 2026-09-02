from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.config import AuthSettings
from app.core.security import InvalidAccessTokenError, decode_access_token
from app.models import User

BEARER_SCHEME = HTTPBearer(auto_error=False)


def get_database_session(request: Request) -> Iterator[Session]:
    engine: Engine | None = request.app.state.db_engine
    if engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=request.app.state.database_error,
        )

    with Session(engine) as session:
        yield session


def get_auth_settings(request: Request) -> AuthSettings:
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
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = decode_access_token(credentials.credentials, auth_settings)
    except InvalidAccessTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
