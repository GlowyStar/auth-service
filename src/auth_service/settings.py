from functools import cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = "postgresql+asyncpg://auth:auth@localhost:5432/auth"
    redis_url: str = "redis://localhost:6379/0"


@cache
def get_settings() -> Settings:
    return Settings()
