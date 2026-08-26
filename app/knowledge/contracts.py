from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


KNOWLEDGE_BASE_PROCESSING_POLICY = "knowledge-base"
CRANE_INTELLIGENCE_SOURCE_APP = "crane-intelligence"

SCOPE_PATTERN = r"^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?$"
CONTEXT_IDENTIFIER_PATTERN = r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9])?$"
LANGUAGE_PATTERN = r"^[a-z]{2}(?:-[A-Z]{2})?$"


class KnowledgeDocumentType(StrEnum):
    MANUAL = "manual"
    TECHNICAL_SPECIFICATION = "technical-specification"
    MAINTENANCE_PROCEDURE = "maintenance-procedure"
    INSPECTION_REPORT = "inspection-report"
    SAFETY_DOCUMENT = "safety-document"
    OTHER = "other"


class KnowledgeDocumentContext(BaseModel):
    """Metadata used for RAG filters and the Bedrock S3 sidecar file."""

    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=CONTEXT_IDENTIFIER_PATTERN,
    )
    component_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=CONTEXT_IDENTIFIER_PATTERN,
    )
    document_type: KnowledgeDocumentType
    document_title: str | None = Field(default=None, min_length=1, max_length=255)
    language: str = Field(default="es", pattern=LANGUAGE_PATTERN)


class KnowledgeRetrieveRequest(BaseModel):
    """Server-side retrieval contract. Tenant and source are derived from auth."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=2, max_length=2_000)
    project_id: str | None = Field(
        default=None, min_length=1, max_length=64, pattern=SCOPE_PATTERN
    )
    asset_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=CONTEXT_IDENTIFIER_PATTERN,
    )
    component_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=CONTEXT_IDENTIFIER_PATTERN,
    )
    max_results: int = Field(default=5, ge=1, le=8)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("query must contain at least two non-whitespace characters")
        return normalized


class KnowledgeCitation(BaseModel):
    """Public citation shape; it intentionally omits the private S3 URI."""

    document_id: UUID
    title: str
    excerpt: str
    score: float = Field(ge=0.0, le=1.0)
    page_number: int | None = Field(default=None, ge=1)


class KnowledgeRetrieveResponse(BaseModel):
    query: str
    citations: list[KnowledgeCitation]


class KnowledgeSyncStatus(StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"

class KnowledgeGenerateMessage(BaseModel):
    """A bounded text-only turn accepted from the server-side chat proxy."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    text: str = Field(min_length=1, max_length=8_000)

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("text must not be blank")
        return normalized


class KnowledgeGenerateRequest(BaseModel):
    """Generation request for the Crane Intelligence server-side proxy."""

    model_config = ConfigDict(extra="forbid")

    system_prompt: str = Field(min_length=1, max_length=60_000)
    messages: list[KnowledgeGenerateMessage] = Field(min_length=1, max_length=24)

    @field_validator("system_prompt")
    @classmethod
    def normalize_system_prompt(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("system_prompt must not be blank")
        return normalized

    @model_validator(mode="after")
    def limit_total_input(self) -> "KnowledgeGenerateRequest":
        total = len(self.system_prompt) + sum(len(message.text) for message in self.messages)
        if total > 60_000:
            raise ValueError("chat input exceeds the configured maximum")
        return self


class KnowledgeGenerateResponse(BaseModel):
    text: str = Field(min_length=1, max_length=16_000)
