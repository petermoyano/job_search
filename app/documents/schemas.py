from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.documents.resume_schemas import ResumeProfileDraftV1
from app.documents.models import DocumentStatus
from app.knowledge.contracts import (
    CRANE_INTELLIGENCE_SOURCE_APP,
    KNOWLEDGE_BASE_PROCESSING_POLICY,
    KnowledgeDocumentContext,
    KnowledgeSyncStatus,
)
from app.radar.models import SearchProfileDocument


SCOPE_PATTERN = r"^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?$"
POLICY_PATTERN = r"^[a-z0-9](?:[a-z0-9._-]{0,98}[a-z0-9])?$"
PROFILE_PATTERN = r"^[a-zA-Z0-9](?:[a-zA-Z0-9._-]{0,253}[a-zA-Z0-9])?$"


class DocumentContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        pattern=PROFILE_PATTERN,
    )

    knowledge: KnowledgeDocumentContext | None = None


class UploadUrlRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=64, pattern=SCOPE_PATTERN)
    project_id: str | None = Field(
        default=None, min_length=1, max_length=64, pattern=SCOPE_PATTERN
    )
    source_app: str = Field(min_length=1, max_length=64, pattern=SCOPE_PATTERN)
    processing_policy: str = Field(min_length=1, max_length=100, pattern=POLICY_PATTERN)
    context: DocumentContext | None = None
    filename: str = Field(min_length=5, max_length=255)
    mime_type: str
    file_size_bytes: int = Field(gt=0)

    @field_validator("filename")
    @classmethod
    def validate_pdf_filename(cls, value: str) -> str:
        filename = value.strip()
        if not filename.casefold().endswith(".pdf"):
            raise ValueError("filename must end in .pdf")
        return filename

    @field_validator("mime_type")
    @classmethod
    def validate_pdf_mime_type(cls, value: str) -> str:
        if value.strip().casefold() != "application/pdf":
            raise ValueError("mime_type must be application/pdf")

        return "application/pdf"

    @model_validator(mode="after")
    def validate_knowledge_base_context(self) -> "UploadUrlRequest":
        has_knowledge_context = (
            self.context is not None and self.context.knowledge is not None
        )
        if self.processing_policy == KNOWLEDGE_BASE_PROCESSING_POLICY:
            if self.source_app != CRANE_INTELLIGENCE_SOURCE_APP:
                raise ValueError(
                    "knowledge-base policy is only available to crane-intelligence"
                )
            if self.project_id is None:
                raise ValueError("knowledge-base policy requires project_id")
            if not has_knowledge_context:
                raise ValueError(
                    "knowledge-base policy requires context.knowledge metadata"
                )
            if self.context is not None and self.context.profile_id is not None:
                raise ValueError(
                    "knowledge-base policy does not allow profile_id context"
                )
        elif has_knowledge_context:
            raise ValueError(
                "knowledge context is only valid for the knowledge-base policy"
            )
        return self


class UploadUrlResponse(BaseModel):
    document_id: UUID
    status: DocumentStatus
    upload_url: str
    expires_in: int
    required_headers: dict[str, str]


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: str
    project_id: str | None
    source_app: str
    processing_policy: str
    context: DocumentContext | None
    filename: str
    mime_type: str
    file_size_bytes: int
    sha256: str | None
    status: DocumentStatus
    classification: str | None
    relevance_score: float | None

    decision: str | None
    result_type: str | None
    result_id: UUID | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    uploaded_at: datetime | None
    knowledge_sync_status: KnowledgeSyncStatus | None


class ResumeProfileDraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    profile_id: str | None
    schema_version: str
    payload: ResumeProfileDraftV1
    model_id: str
    extracted_at: datetime
    created_at: datetime
    updated_at: datetime
    applied_at: datetime | None


class ResumeApplySection(StrEnum):
    full_name = "full_name"
    headline = "headline"
    professional_summary = "professional_summary"
    location = "location"
    skills = "skills"
    experience = "experience"
    education = "education"
    languages = "languages"
    certifications = "certifications"


class ApplyResumeDraftRequest(BaseModel):
    profile_id: str = Field(
        min_length=1,
        max_length=255,
        pattern=PROFILE_PATTERN,
    )
    sections: list[ResumeApplySection] = Field(min_length=1)
    expected_revision: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_unique_sections(self) -> "ApplyResumeDraftRequest":
        if len(set(self.sections)) != len(self.sections):
            raise ValueError("sections must not contain duplicates")
        return self


class ApplyResumeDraftResponse(SearchProfileDocument):
    applied_draft_id: UUID
    applied_at: datetime
