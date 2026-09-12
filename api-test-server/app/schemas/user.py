"""用户对外响应模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserResponse(BaseModel):
    """仅暴露安全的用户公开字段，不包含 password_hash。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    is_active: bool
    created_at: datetime
