from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_ssm_parameter(name: str) -> str:
    import boto3  # type: ignore[import-untyped]

    response = boto3.client("ssm").get_parameter(Name=name, WithDecryption=True)
    value = response.get("Parameter", {}).get("Value")
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"SSM parameter {name!r} did not contain a value")
    return value


def _normalize_database_url(value: str) -> str:
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_env: Literal["local", "test", "production"] = "local"
    database_url: str = Field(default="sqlite:///./job_radar.db", repr=False)
    database_url_ssm_parameter: str | None = Field(default=None, repr=False)
    openai_api_key: str | None = Field(default=None, repr=False)
    tavily_api_key: str | None = Field(default=None, repr=False)
    llm_model: str = "gpt-4.1-mini"
    initialize_database: bool = True
    aws_region: str = "sa-east-1"
    documents_s3_bucket: str = "local-documents"
    documents_max_file_size_bytes: int = 20 * 1024 * 1024
    documents_upload_url_expires_seconds: int = 900
    document_client_secret_ids: str = ""
    document_client_keys_json: str | None = Field(default=None, repr=False)
    document_auth_cache_ttl_seconds: int = 300
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "https://job-search-fe.vercel.app",
        ]
    )
    cors_origin_regex: str | None = (
        r"^https://job-search-[a-z0-9-]+-petermoyanos-projects\.vercel\.app$"
    )

    @model_validator(mode="after")
    def resolve_database_url(self) -> "Settings":
        database_url = self.database_url
        if self.database_url_ssm_parameter:
            database_url = _get_ssm_parameter(self.database_url_ssm_parameter)
        self.database_url = _normalize_database_url(database_url)
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
