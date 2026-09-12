"""服务端环境配置模型。

Pydantic Settings 从系统环境变量或本地 .env 读取配置，SecretStr 避免密码和
JWT 密钥在对象 repr 中意外出现在日志里。
"""

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvironmentSettings(BaseSettings):
    """所有服务端配置共享的读取规则。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        str_strip_whitespace=True,
    )


class Settings(EnvironmentSettings):
    """数据库连接配置。"""

    db_host: str = Field(min_length=1)
    db_port: int = Field(default=3306, ge=1, le=65535)
    db_user: str = Field(min_length=1)
    db_password: SecretStr = Field(min_length=1)
    db_name: str = Field(min_length=1)


class AuthSettings(EnvironmentSettings):
    """JWT 签名算法、密钥和访问令牌有效期配置。"""

    jwt_secret_key: SecretStr = Field(min_length=32)
    jwt_algorithm: Literal["HS256"] = "HS256"
    access_token_expire_minutes: int = Field(default=30, gt=0, le=1440)
