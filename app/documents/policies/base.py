from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.documents.models import DocumentStatus


class PolicyTransientError(Exception):
    pass


class DocumentProcessingPolicy(Protocol):
    policy_name: str

    def process(
        self,
        *,
        document_id: UUID,
        attempt_started_at: datetime | None,
        document_bytes: bytes | None,
    ) -> DocumentStatus: ...
