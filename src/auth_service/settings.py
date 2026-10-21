from functools import cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = "postgresql+asyncpg://auth:auth@localhost:5432/auth"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: SecretStr = Field(min_length=32)
    access_token_ttl_seconds: int = 15 * 60
    refresh_token_ttl_days: int = 30

    email_backend: Literal["console", "smtp"] = "console"
    email_from: str = "no-reply@example.com"
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None


@cache
def get_settings() -> Settings:
    return Settings()
