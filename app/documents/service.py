from __future__ import annotations

from dataclasses import dataclass
import logging
from uuid import UUID, uuid4

from app.core.config import Settings
from app.documents.auth import AuthContext
from app.documents.models import Document, DocumentStatus, now_utc
from app.documents.queue import (
    DocumentProcessingQueue,
    QueueUnavailableError,
)
from app.documents.repository import DocumentRepository
from app.documents.schemas import UploadUrlRequest
from app.documents.storage import (
    DocumentStorage,
    ObjectNotFoundError,
    PresignedUpload,
    StorageUnavailableError,
)


LOGGER = logging.getLogger(__name__)


class DocumentAccessDeniedError(Exception):
    pass


class DocumentNotFoundError(Exception):
    pass


class FileTooLargeError(Exception):
    pass


class InvalidUploadStateError(Exception):
    pass


class UploadObjectNotFoundError(Exception):
    pass


class UploadValidationError(Exception):
    pass


@dataclass(frozen=True)
class CreatedUpload:
    document: Document
    upload: PresignedUpload
    expires_in: int


def build_s3_key(
    *,
    tenant_id: str,
    source_app: str,
    project_id: str | None,
    document_id: UUID,
) -> str:
    project_segment = project_id or "default"
    return (
        f"documents/{tenant_id}/{source_app}/{project_segment}/"
        f"{document_id}/original.pdf"
    )


class DocumentService:
    def __init__(
        self,
        *,
        repository: DocumentRepository,
        storage: DocumentStorage,
        processing_queue: DocumentProcessingQueue,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.processing_queue = processing_queue
        self.settings = settings

    def create_upload(
        self, *, payload: UploadUrlRequest, auth_context: AuthContext
    ) -> CreatedUpload:
        self._authorize_scope(
            auth_context=auth_context,
            tenant_id=payload.tenant_id,
            source_app=payload.source_app,
        )
        if payload.file_size_bytes > self.settings.documents_max_file_size_bytes:
            raise FileTooLargeError(
                f"PDF exceeds the {self.settings.documents_max_file_size_bytes} byte limit"
            )

        document_id = uuid4()
        document = Document(
            id=document_id,
            tenant_id=payload.tenant_id,
            project_id=payload.project_id,
            source_app=payload.source_app,
            processing_policy=payload.processing_policy,
            original_filename=payload.filename,
            mime_type=payload.mime_type,
            file_size_bytes=payload.file_size_bytes,
            s3_bucket=self.settings.documents_s3_bucket,
            s3_key=build_s3_key(
                tenant_id=payload.tenant_id,
                source_app=payload.source_app,
                project_id=payload.project_id,
                document_id=document_id,
            ),
            status=DocumentStatus.PENDING_UPLOAD,
        )
        self.repository.add(document)

        try:
            upload = self.storage.create_upload_url(
                bucket=document.s3_bucket,
                key=document.s3_key,
                document_id=document.id,
                file_size_bytes=document.file_size_bytes,
                expires_in=self.settings.documents_upload_url_expires_seconds,
            )
        except StorageUnavailableError:
            document.status = DocumentStatus.FAILED
            document.error_code = "PRESIGNED_URL_FAILED"
            document.error_message = "Could not prepare document upload"
            self.repository.commit()
            LOGGER.exception(
                "event=upload_validation_failed document_id=%s tenant_id=%s "
                "source_app=%s status=%s error_code=%s",
                document.id,
                document.tenant_id,
                document.source_app,
                document.status,
                document.error_code,
            )
            raise

        self.repository.commit()
        self.repository.refresh(document)
        LOGGER.info(
            "event=document_created document_id=%s tenant_id=%s source_app=%s status=%s",
            document.id,
            document.tenant_id,
            document.source_app,
            document.status,
        )
        LOGGER.info(
            "event=presigned_url_generated document_id=%s tenant_id=%s "
            "source_app=%s status=%s expires_in=%s",
            document.id,
            document.tenant_id,
            document.source_app,
            document.status,
            self.settings.documents_upload_url_expires_seconds,
        )
        return CreatedUpload(
            document=document,
            upload=upload,
            expires_in=self.settings.documents_upload_url_expires_seconds,
        )

    def complete_upload(
        self, *, document_id: UUID, auth_context: AuthContext
    ) -> Document:
        document = self._get_scoped(
            document_id=document_id,
            auth_context=auth_context,
            for_update=True,
        )
        if document.status == DocumentStatus.UPLOADED:
            if document.processing_enqueued_at is None:
                self._enqueue_processing(document)
            return document
        if document.status != DocumentStatus.PENDING_UPLOAD:
            if document.uploaded_at is not None:
                return document
            raise InvalidUploadStateError(
                f"Upload cannot be completed from {document.status}"
            )

        try:
            stored_object = self.storage.head_object(
                bucket=document.s3_bucket, key=document.s3_key
            )
        except ObjectNotFoundError as exc:
            LOGGER.warning(
                "event=upload_validation_failed document_id=%s tenant_id=%s "
                "source_app=%s status=%s error_code=OBJECT_NOT_FOUND",
                document.id,
                document.tenant_id,
                document.source_app,
                document.status,
            )
            raise UploadObjectNotFoundError("Uploaded object does not exist") from exc

        failures: list[tuple[str, str]] = []
        if stored_object.size_bytes != document.file_size_bytes:
            failures.append(
                (
                    "SIZE_MISMATCH",
                    "Uploaded object size does not match the declared size",
                )
            )
        if (
            stored_object.content_type is not None
            and stored_object.content_type.casefold() != document.mime_type.casefold()
        ):
            failures.append(
                (
                    "CONTENT_TYPE_MISMATCH",
                    "Uploaded object Content-Type is not application/pdf",
                )
            )
        if stored_object.metadata.get("document-id") != str(document.id):
            failures.append(
                (
                    "DOCUMENT_ID_MISMATCH",
                    "Uploaded object metadata does not match the document",
                )
            )
        if failures:
            error_code, error_message = failures[0]
            document.status = DocumentStatus.FAILED
            document.error_code = error_code
            document.error_message = error_message
            self.repository.commit()
            LOGGER.warning(
                "event=upload_validation_failed document_id=%s tenant_id=%s "
                "source_app=%s status=%s error_code=%s",
                document.id,
                document.tenant_id,
                document.source_app,
                document.status,
                document.error_code,
            )
            raise UploadValidationError(error_message)

        document.status = DocumentStatus.UPLOADED
        document.uploaded_at = now_utc()
        document.error_code = None
        document.error_message = None
        self._enqueue_processing(document)
        LOGGER.info(
            "event=upload_completed document_id=%s tenant_id=%s source_app=%s status=%s",
            document.id,
            document.tenant_id,
            document.source_app,
            document.status,
        )
        return document

    def _enqueue_processing(self, document: Document) -> None:
        try:
            self.processing_queue.enqueue(document_id=document.id)
        except QueueUnavailableError:
            self.repository.rollback()
            LOGGER.exception(
                "event=document_processing_failed_transient document_id=%s "
                "tenant_id=%s source_app=%s previous_status=%s "
                "error_code=QUEUE_UNAVAILABLE",
                document.id,
                document.tenant_id,
                document.source_app,
                document.status,
            )
            raise
        document.processing_enqueued_at = now_utc()
        self.repository.commit()
        self.repository.refresh(document)
        LOGGER.info(
            "event=document_processing_enqueued document_id=%s tenant_id=%s "
            "source_app=%s status=%s",
            document.id,
            document.tenant_id,
            document.source_app,
            document.status,
        )

    def get_document(self, *, document_id: UUID, auth_context: AuthContext) -> Document:
        return self._get_scoped(
            document_id=document_id,
            auth_context=auth_context,
            for_update=False,
        )

    def _get_scoped(
        self,
        *,
        document_id: UUID,
        auth_context: AuthContext,
        for_update: bool,
    ) -> Document:
        document = self.repository.get_scoped(
            document_id=document_id,
            auth_context=auth_context,
            for_update=for_update,
        )
        if document is None:
            LOGGER.warning(
                "event=document_access_denied document_id=%s source_app=%s",
                document_id,
                auth_context.source_app,
            )
            raise DocumentNotFoundError("Document not found")
        return document

    @staticmethod
    def _authorize_scope(
        *, auth_context: AuthContext, tenant_id: str, source_app: str
    ) -> None:
        if not auth_context.allows(source_app=source_app, tenant_id=tenant_id):
            LOGGER.warning(
                "event=document_access_denied tenant_id=%s requested_source_app=%s "
                "credential_source_app=%s",
                tenant_id,
                source_app,
                auth_context.source_app,
            )
            raise DocumentAccessDeniedError(
                "Credential is not authorized for this document scope"
            )
