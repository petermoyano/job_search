from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from hashlib import sha256
import logging
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.documents.models import Document, DocumentStatus, now_utc
from app.documents.repository import DocumentRepository
from app.documents.storage import (
    DocumentStorage,
    ObjectNotFoundError,
    StorageUnavailableError,
)


LOGGER = logging.getLogger(__name__)


class ProcessingOutcome(StrEnum):
    PREPROCESSED = "PREPROCESSED"
    SKIPPED = "SKIPPED"
    NOT_FOUND = "NOT_FOUND"


@dataclass(frozen=True)
class ProcessingResult:
    document_id: UUID
    outcome: ProcessingOutcome
    status: DocumentStatus | None


class PermanentDocumentError(Exception):
    def __init__(self, *, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message


class TransientProcessingError(Exception):
    pass


def _normalized_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class DocumentProcessingService:
    def __init__(
        self,
        *,
        repository: DocumentRepository,
        storage: DocumentStorage,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.settings = settings

    def process(self, *, document_id: UUID) -> ProcessingResult:
        started_at = now_utc()
        stale_before = started_at - timedelta(
            seconds=self.settings.document_processing_lease_seconds
        )
        try:
            document, claimed, previous_status = self.repository.claim_for_processing(
                document_id=document_id,
                started_at=started_at,
                stale_before=stale_before,
            )
        except SQLAlchemyError as exc:
            self.repository.rollback()
            self._log_transient(document_id=document_id, error_code="DATABASE_CLAIM")
            raise TransientProcessingError("Could not claim document") from exc

        if document is None:
            LOGGER.warning(
                "event=document_processing_skipped document_id=%s reason=NOT_FOUND",
                document_id,
            )
            return ProcessingResult(
                document_id=document_id,
                outcome=ProcessingOutcome.NOT_FOUND,
                status=None,
            )
        if not claimed:
            LOGGER.info(
                "event=document_processing_skipped document_id=%s tenant_id=%s "
                "source_app=%s previous_status=%s reason=NOT_ELIGIBLE",
                document.id,
                document.tenant_id,
                document.source_app,
                previous_status,
            )
            return ProcessingResult(
                document_id=document.id,
                outcome=ProcessingOutcome.SKIPPED,
                status=document.status,
            )

        attempt_started_at = document.processing_started_at
        LOGGER.info(
            "event=document_processing_started document_id=%s tenant_id=%s "
            "source_app=%s previous_status=%s new_status=%s",
            document.id,
            document.tenant_id,
            document.source_app,
            previous_status,
            DocumentStatus.PROCESSING,
        )

        try:
            content = self.storage.read_object(
                bucket=document.s3_bucket,
                key=document.s3_key,
            )
            self._validate_content(document=document, content=content)
            digest = sha256(content.body).hexdigest()
            LOGGER.info(
                "event=document_sha256_calculated document_id=%s tenant_id=%s "
                "source_app=%s",
                document.id,
                document.tenant_id,
                document.source_app,
            )
            self._mark_preprocessed(
                document_id=document.id,
                attempt_started_at=attempt_started_at,
                digest=digest,
            )
        except ObjectNotFoundError:
            return self._handle_permanent(
                document=document,
                attempt_started_at=attempt_started_at,
                error=PermanentDocumentError(
                    code="OBJECT_NOT_FOUND",
                    message="Document object does not exist",
                ),
            )
        except PermanentDocumentError as exc:
            return self._handle_permanent(
                document=document,
                attempt_started_at=attempt_started_at,
                error=exc,
            )
        except StorageUnavailableError as exc:
            self._release_for_retry(
                document=document,
                attempt_started_at=attempt_started_at,
                error_code="S3_UNAVAILABLE",
            )
            raise TransientProcessingError("Document storage unavailable") from exc
        except SQLAlchemyError as exc:
            self.repository.rollback()
            self._log_transient(
                document_id=document.id,
                tenant_id=document.tenant_id,
                source_app=document.source_app,
                error_code="DATABASE_UPDATE",
            )
            raise TransientProcessingError("Could not update document") from exc

        LOGGER.info(
            "event=document_preprocessed document_id=%s tenant_id=%s source_app=%s "
            "previous_status=%s new_status=%s",
            document.id,
            document.tenant_id,
            document.source_app,
            DocumentStatus.PROCESSING,
            DocumentStatus.PREPROCESSED,
        )
        return ProcessingResult(
            document_id=document.id,
            outcome=ProcessingOutcome.PREPROCESSED,
            status=DocumentStatus.PREPROCESSED,
        )

    def _validate_content(self, *, document: Document, content) -> None:
        if content.size_bytes <= 0 or not content.body:
            raise PermanentDocumentError(
                code="EMPTY_FILE",
                message="Document object is empty",
            )
        if content.size_bytes > self.settings.documents_max_file_size_bytes:
            raise PermanentDocumentError(
                code="FILE_TOO_LARGE",
                message="Document object exceeds the configured size limit",
            )
        if content.size_bytes != len(content.body):
            raise PermanentDocumentError(
                code="INCOMPLETE_OBJECT",
                message="Document object length is inconsistent",
            )
        if content.size_bytes != document.file_size_bytes:
            raise PermanentDocumentError(
                code="SIZE_MISMATCH",
                message="Document object size does not match its metadata",
            )
        if content.metadata.get("document-id") != str(document.id):
            raise PermanentDocumentError(
                code="DOCUMENT_ID_MISMATCH",
                message="Document object metadata does not match the document",
            )
        if not content.body.startswith(b"%PDF-"):
            raise PermanentDocumentError(
                code="INVALID_PDF_SIGNATURE",
                message="Document object does not have a valid PDF signature",
            )
        LOGGER.info(
            "event=document_pdf_validated document_id=%s tenant_id=%s source_app=%s",
            document.id,
            document.tenant_id,
            document.source_app,
        )

    def _mark_preprocessed(
        self,
        *,
        document_id: UUID,
        attempt_started_at: datetime | None,
        digest: str,
    ) -> None:
        current = self.repository.get_for_processing(
            document_id=document_id,
            for_update=True,
        )
        if not self._owns_attempt(current, attempt_started_at):
            self.repository.rollback()
            raise TransientProcessingError("Processing claim changed")
        current.sha256 = digest
        current.status = DocumentStatus.PREPROCESSED
        current.preprocessed_at = now_utc()
        current.processing_started_at = None
        current.error_code = None
        current.error_message = None
        self.repository.commit()

    def _handle_permanent(
        self,
        *,
        document: Document,
        attempt_started_at: datetime | None,
        error: PermanentDocumentError,
    ) -> ProcessingResult:
        try:
            current = self.repository.get_for_processing(
                document_id=document.id,
                for_update=True,
            )
            if self._owns_attempt(current, attempt_started_at):
                current.status = DocumentStatus.FAILED
                current.processing_started_at = None
                current.error_code = error.code
                current.error_message = error.safe_message
                self.repository.commit()
            else:
                self.repository.rollback()
        except SQLAlchemyError as exc:
            self.repository.rollback()
            self._log_transient(
                document_id=document.id,
                tenant_id=document.tenant_id,
                source_app=document.source_app,
                error_code="DATABASE_FAILURE_STATE",
            )
            raise TransientProcessingError(
                "Could not persist permanent document failure"
            ) from exc
        LOGGER.warning(
            "event=document_processing_failed_permanent document_id=%s tenant_id=%s "
            "source_app=%s previous_status=%s new_status=%s error_code=%s",
            document.id,
            document.tenant_id,
            document.source_app,
            DocumentStatus.PROCESSING,
            DocumentStatus.FAILED,
            error.code,
        )
        return ProcessingResult(
            document_id=document.id,
            outcome=ProcessingOutcome.SKIPPED,
            status=DocumentStatus.FAILED,
        )

    def _release_for_retry(
        self,
        *,
        document: Document,
        attempt_started_at: datetime | None,
        error_code: str,
    ) -> None:
        try:
            current = self.repository.get_for_processing(
                document_id=document.id,
                for_update=True,
            )
            if self._owns_attempt(current, attempt_started_at):
                current.status = DocumentStatus.UPLOADED
                current.processing_started_at = None
                self.repository.commit()
            else:
                self.repository.rollback()
        except SQLAlchemyError:
            self.repository.rollback()
        self._log_transient(
            document_id=document.id,
            tenant_id=document.tenant_id,
            source_app=document.source_app,
            error_code=error_code,
        )

    @staticmethod
    def _owns_attempt(
        document: Document | None,
        attempt_started_at: datetime | None,
    ) -> bool:
        return (
            document is not None
            and document.status == DocumentStatus.PROCESSING
            and _normalized_timestamp(document.processing_started_at)
            == _normalized_timestamp(attempt_started_at)
        )

    @staticmethod
    def _log_transient(
        *,
        document_id: UUID,
        error_code: str,
        tenant_id: str | None = None,
        source_app: str | None = None,
    ) -> None:
        LOGGER.warning(
            "event=document_processing_failed_transient document_id=%s "
            "tenant_id=%s source_app=%s error_code=%s",
            document_id,
            tenant_id,
            source_app,
            error_code,
        )
