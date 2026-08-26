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
from app.documents.policies.base import (
    DocumentProcessingPolicy,
    PolicyTransientError,
)
from app.documents.policies.resume import build_resume_processing_policy
from app.documents.repository import DocumentRepository
from app.documents.storage import (
    DocumentStorage,
    ObjectNotFoundError,
    StorageUnavailableError,
)
from app.knowledge.ingestion import (
    KnowledgeIngestionPermanentError,
    KnowledgeIngestionRequest,
    KnowledgeIngestionService,
    KnowledgeIngestionTransientError,
)
from app.knowledge.contracts import (
    CRANE_INTELLIGENCE_SOURCE_APP,
    KNOWLEDGE_BASE_PROCESSING_POLICY,
)


LOGGER = logging.getLogger(__name__)


class ProcessingOutcome(StrEnum):
    PREPROCESSED = "PREPROCESSED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    FAILED = "FAILED"
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
        resume_policy: DocumentProcessingPolicy | None = None,
        knowledge_ingestion_service: KnowledgeIngestionService | None = None,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.settings = settings
        self.resume_policy = resume_policy
        self.knowledge_ingestion_service = knowledge_ingestion_service

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
            document.status,
        )

        resume_enabled = self._is_resume_policy(document)
        knowledge_enabled = self._is_knowledge_base_policy(document)
        if document.status != DocumentStatus.PROCESSING:
            return self._run_resume_policy(
                document_id=document.id,
                attempt_started_at=attempt_started_at,
                document_bytes=None,
            )

        knowledge_request: KnowledgeIngestionRequest | None = None
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
            if knowledge_enabled:
                knowledge_request = self._request_knowledge_sync(
                    document=document,
                    document_sha256=digest,
                )
            self._mark_preprocessed(
                document_id=document.id,
                attempt_started_at=attempt_started_at,
                digest=digest,
                keep_lease=resume_enabled,
                knowledge_request=knowledge_request,
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
        except KnowledgeIngestionPermanentError as exc:
            return self._handle_permanent(
                document=document,
                attempt_started_at=attempt_started_at,
                error=PermanentDocumentError(
                    code=exc.code,
                    message=exc.safe_message,
                ),
            )
        except KnowledgeIngestionTransientError as exc:
            self._release_for_retry(
                document=document,
                attempt_started_at=attempt_started_at,
                error_code="KNOWLEDGE_INGESTION_UNAVAILABLE",
            )
            raise TransientProcessingError(
                "Knowledge Base ingestion is temporarily unavailable"
            ) from exc
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
        if resume_enabled:
            return self._run_resume_policy(
                document_id=document.id,
                attempt_started_at=attempt_started_at,
                document_bytes=content.body,
            )
        return ProcessingResult(
            document_id=document.id,
            outcome=ProcessingOutcome.PREPROCESSED,
            status=DocumentStatus.PREPROCESSED,
        )

    def _run_resume_policy(
        self,
        *,
        document_id: UUID,
        attempt_started_at: datetime | None,
        document_bytes: bytes | None,
    ) -> ProcessingResult:
        policy = self.resume_policy or build_resume_processing_policy(
            repository=self.repository,
            storage=self.storage,
            settings=self.settings,
        )
        try:
            result_status = policy.process(
                document_id=document_id,
                attempt_started_at=attempt_started_at,
                document_bytes=document_bytes,
            )
        except PolicyTransientError as exc:
            raise TransientProcessingError(
                "Resume policy is temporarily unavailable"
            ) from exc
        outcomes = {
            DocumentStatus.COMPLETED: ProcessingOutcome.COMPLETED,
            DocumentStatus.REJECTED: ProcessingOutcome.REJECTED,
            DocumentStatus.NEEDS_REVIEW: ProcessingOutcome.NEEDS_REVIEW,
            DocumentStatus.FAILED: ProcessingOutcome.FAILED,
            DocumentStatus.PREPROCESSED: ProcessingOutcome.PREPROCESSED,
        }
        return ProcessingResult(
            document_id=document_id,
            outcome=outcomes.get(result_status, ProcessingOutcome.SKIPPED),
            status=result_status,
        )

    @staticmethod
    def _is_resume_policy(document: Document) -> bool:
        return (
            document.source_app == "job-search"
            and document.processing_policy == "resume"
        )

    @staticmethod
    def _is_knowledge_base_policy(document: Document) -> bool:
        return (
            document.source_app == CRANE_INTELLIGENCE_SOURCE_APP
            and document.processing_policy == KNOWLEDGE_BASE_PROCESSING_POLICY
        )

    def _request_knowledge_sync(
        self,
        *,
        document: Document,
        document_sha256: str,
    ) -> KnowledgeIngestionRequest:
        service = self.knowledge_ingestion_service
        if service is None:
            service = KnowledgeIngestionService(
                storage=self.storage,
                settings=self.settings,
            )
            self.knowledge_ingestion_service = service
        return service.request_sync(
            document=document,
            document_sha256=document_sha256,
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
        keep_lease: bool,
        knowledge_request: KnowledgeIngestionRequest | None,
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
        if knowledge_request is not None:
            current.knowledge_sync_status = knowledge_request.status
            current.knowledge_ingestion_job_id = knowledge_request.ingestion_job_id
            current.knowledge_sync_requested_at = knowledge_request.requested_at
            current.knowledge_sync_completed_at = None
        if not keep_lease:
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
