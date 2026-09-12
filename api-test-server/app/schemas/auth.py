"""认证接口的 Pydantic 请求与响应模型。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """注册输入：用户名格式、邮箱和密码长度在进入 Service 前校验。"""

    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """登录输入；认证失败统一由 Service 返回 401，避免暴露用户是否存在。"""

    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """登录成功后的最小令牌响应，不返回用户密码或密码哈希。"""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
