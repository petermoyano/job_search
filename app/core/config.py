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
    document_processing_queue_url: str = ""
    document_processing_lease_seconds: int = 300
    radar_quality_review_queue_url: str = ""
    radar_quality_review_rubric_version: str = "v1"
    radar_quality_review_model_id: str = "mistral.ministral-3-14b-instruct"
    radar_quality_review_bedrock_region: str = "sa-east-1"
    radar_quality_review_connect_timeout_seconds: int = Field(default=5, gt=0)
    radar_quality_review_read_timeout_seconds: int = Field(default=45, gt=0)
    radar_search_review_model_id: str = "mistral.ministral-3-14b-instruct"
    radar_search_review_bedrock_region: str = "sa-east-1"
    radar_search_review_connect_timeout_seconds: int = Field(default=5, gt=0)
    radar_search_review_read_timeout_seconds: int = Field(default=45, gt=0)
    radar_search_review_max_output_tokens: int = Field(default=900, ge=128, le=2_048)
    radar_quality_review_lease_seconds: int = Field(default=300, gt=0)
    radar_quality_review_outbox_batch_size: int = Field(default=25, ge=1, le=100)
    resume_processing_model_id: str = "mistral.ministral-3-14b-instruct"
    resume_processing_bedrock_region: str = "sa-east-1"
    resume_min_extracted_characters: int = Field(default=100, gt=0)
    resume_max_model_input_characters: int = Field(default=60_000, gt=0)
    resume_accept_confidence: float = Field(default=0.80, ge=0.0, le=1.0)
    resume_reject_low_confidence: float = Field(default=0.40, ge=0.0, le=1.0)
    resume_not_resume_reject_confidence: float = Field(default=0.80, ge=0.0, le=1.0)
    resume_bedrock_connect_timeout_seconds: int = Field(default=5, gt=0)
    resume_bedrock_read_timeout_seconds: int = Field(default=45, gt=0)
    knowledge_base_id: str = ""
    knowledge_base_data_source_id: str = ""
    knowledge_base_region: str = "sa-east-1"
    knowledge_base_connect_timeout_seconds: int = Field(default=5, gt=0)
    knowledge_base_read_timeout_seconds: int = Field(default=30, gt=0)
    crane_chat_model_id: str = "mistral.ministral-3-3b-instruct"
    crane_chat_bedrock_region: str = "sa-east-1"
    crane_chat_max_input_characters: int = Field(default=60_000, gt=0)
    crane_chat_max_output_tokens: int = Field(default=700, ge=64, le=2_048)
    crane_chat_connect_timeout_seconds: int = Field(default=5, gt=0)
    crane_chat_read_timeout_seconds: int = Field(default=45, gt=0)
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
        if (
            self.resume_max_model_input_characters
            < self.resume_min_extracted_characters
        ):
            raise ValueError("resume model input maximum must be at least the minimum")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
