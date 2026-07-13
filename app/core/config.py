from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_env: Literal["local", "test", "production"] = "local"
    database_url: str = "sqlite:///./job_radar.db"
    openai_api_key: str | None = Field(default=None, repr=False)
    tavily_api_key: str | None = Field(default=None, repr=False)
    llm_model: str = "gpt-4.1-mini"
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
