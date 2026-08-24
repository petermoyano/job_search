from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.documents.models import DocumentStatus


SCOPE_PATTERN = r"^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?$"
POLICY_PATTERN = r"^[a-z0-9](?:[a-z0-9._-]{0,98}[a-z0-9])?$"


class UploadUrlRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=64, pattern=SCOPE_PATTERN)
    project_id: str | None = Field(
        default=None, min_length=1, max_length=64, pattern=SCOPE_PATTERN
    )
    source_app: str = Field(min_length=1, max_length=64, pattern=SCOPE_PATTERN)
    processing_policy: str = Field(min_length=1, max_length=100, pattern=POLICY_PATTERN)
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
    filename: str
    mime_type: str
    file_size_bytes: int
    status: DocumentStatus
    classification: str | None
    relevance_score: float | None
    decision: str | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    uploaded_at: datetime | None
