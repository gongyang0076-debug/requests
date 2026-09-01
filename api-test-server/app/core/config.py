from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load database settings from environment variables or a local .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        str_strip_whitespace=True,
    )

    db_host: str = Field(min_length=1)
    db_port: int = Field(default=3306, ge=1, le=65535)
    db_user: str = Field(min_length=1)
    db_password: SecretStr = Field(min_length=1)
    db_name: str = Field(min_length=1)
