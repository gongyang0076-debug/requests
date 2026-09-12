"""当前登录用户相关路由。"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.models import User
from app.schemas.user import UserResponse

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
def get_me(current_user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    """返回 JWT 对应的当前用户公开信息。"""

    return UserResponse.model_validate(current_user)
