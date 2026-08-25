from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import logging
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.documents.bedrock.client import (
    BedrockPermanentError,
    BedrockStructuredClient,
    BedrockTransientError,
)
from app.documents.bedrock.resume import ResumeClassifier, ResumeExtractor
from app.documents.models import (
    Document,
    DocumentStatus,
    ResumeProfileDraft,
    now_utc,
)
from app.documents.pdf_text import PdfTextExtractionError, PdfTextExtractor
from app.documents.policies.base import PolicyTransientError
from app.documents.repository import DocumentRepository
from app.documents.storage import (
    DocumentStorage,
    ObjectNotFoundError,
    StorageUnavailableError,
)


LOGGER = logging.getLogger(__name__)
SCHEMA_VERSION = "resume_profile_draft_v1"


def _normalized_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class ResumeProcessingPolicy:
    policy_name = "resume"

    def __init__(
        self,
        *,
        repository: DocumentRepository,
        storage: DocumentStorage,
        settings: Settings,
        classifier: ResumeClassifier,
        extractor: ResumeExtractor,
        text_extractor: PdfTextExtractor,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.settings = settings
        self.classifier = classifier
        self.extractor = extractor
        self.text_extractor = text_extractor

    def process(
        self,
        *,
        document_id: UUID,
        attempt_started_at: datetime | None,
        document_bytes: bytes | None,
    ) -> DocumentStatus:
        try:
            document = self.repository.get_for_processing(
                document_id=document_id,
                for_update=True,
            )
            if document is None:
                self.repository.rollback()
                return DocumentStatus.FAILED
            starting_status = document.status
            self.repository.commit()

            if starting_status == DocumentStatus.DATA_EXTRACTED:
                return self._complete(
                    document_id=document_id,
                    attempt_started_at=attempt_started_at,
                )
            if starting_status not in {
                DocumentStatus.PREPROCESSED,
                DocumentStatus.ACCEPTED,
            }:
                return starting_status

            try:
                extracted_text = self._extract_text(
                    document=document,
                    document_bytes=document_bytes,
                )
            except PdfTextExtractionError as exc:
                return self._mark_failed(
                    document_id=document_id,
                    attempt_started_at=attempt_started_at,
                    code=exc.code,
                    message=exc.safe_message,
                )
            except ObjectNotFoundError:
                return self._mark_failed(
                    document_id=document_id,
                    attempt_started_at=attempt_started_at,
                    code="OBJECT_NOT_FOUND",
                    message="Document object does not exist",
                )
            except StorageUnavailableError as exc:
                self._release_for_retry(
                    document_id=document_id,
                    attempt_started_at=attempt_started_at,
                    stable_status=starting_status,
                    error_code="S3_UNAVAILABLE",
                )
                raise PolicyTransientError("Document storage unavailable") from exc

            LOGGER.info(
                "event=document_text_extracted document_id=%s model_id=%s "
                "page_count=%s input_character_count=%s total_character_count=%s "
                "truncated=%s",
                document_id,
                self.settings.resume_processing_model_id,
                extracted_text.page_count,
                extracted_text.input_characters,
                extracted_text.total_characters,
                extracted_text.truncated,
            )

            if starting_status == DocumentStatus.PREPROCESSED:
                classification_status = self._classify(
                    document_id=document_id,
                    attempt_started_at=attempt_started_at,
                    document_text=extracted_text.text,
                )
                if classification_status != DocumentStatus.ACCEPTED:
                    return classification_status

            return self._extract_profile(
                document_id=document_id,
                attempt_started_at=attempt_started_at,
                document_text=extracted_text.text,
            )
        except PolicyTransientError:
            raise
        except SQLAlchemyError as exc:
            self.repository.rollback()
            LOGGER.warning(
                "event=document_processing_failed_transient document_id=%s "
                "error_code=DATABASE_POLICY",
                document_id,
            )
            raise PolicyTransientError("Could not persist resume processing") from exc

    def _extract_text(
        self,
        *,
        document: Document,
        document_bytes: bytes | None,
    ):
        content = document_bytes
        if content is None:
            stored = self.storage.read_object(
                bucket=document.s3_bucket,
                key=document.s3_key,
            )
            content = stored.body
            if document.sha256 and sha256(content).hexdigest() != document.sha256:
                raise PdfTextExtractionError(
                    code="OBJECT_CHANGED_AFTER_PREPROCESSING",
                    message="Document object changed after preprocessing",
                )
        return self.text_extractor.extract(content)

    def _classify(
        self,
        *,
        document_id: UUID,
        attempt_started_at: datetime | None,
        document_text: str,
    ) -> DocumentStatus:
        document = self._locked_owned(
            document_id=document_id,
            attempt_started_at=attempt_started_at,
            expected_status=DocumentStatus.PREPROCESSED,
        )
        document.status = DocumentStatus.CLASSIFYING
        self.repository.commit()
        LOGGER.info(
            "event=resume_classification_started document_id=%s model_id=%s "
            "input_character_count=%s",
            document_id,
            self.settings.resume_processing_model_id,
            len(document_text),
        )
        try:
            classified = self.classifier.classify(document_text)
        except BedrockTransientError as exc:
            self._release_for_retry(
                document_id=document_id,
                attempt_started_at=attempt_started_at,
                stable_status=DocumentStatus.PREPROCESSED,
                error_code="BEDROCK_TRANSIENT",
            )
            raise PolicyTransientError("Bedrock classification unavailable") from exc
        except BedrockPermanentError as exc:
            LOGGER.warning(
                "event=bedrock_permanent_error document_id=%s model_id=%s "
                "error_code=%s",
                document_id,
                self.settings.resume_processing_model_id,
                exc.code,
            )
            return self._mark_failed(
                document_id=document_id,
                attempt_started_at=attempt_started_at,
                code=f"BEDROCK_{exc.code}"[:100],
                message=exc.safe_message,
            )

        value = classified.value
        status, decision, classification = self._classification_decision(
            is_resume=value.is_resume,
            confidence=value.confidence,
        )
        document = self._locked_owned(
            document_id=document_id,
            attempt_started_at=attempt_started_at,
            expected_status=DocumentStatus.CLASSIFYING,
        )
        document.classification = classification
        document.relevance_score = value.confidence
        document.decision = decision
        document.status = status
        if status in {DocumentStatus.REJECTED, DocumentStatus.NEEDS_REVIEW}:
            document.processing_started_at = None
        self.repository.commit()
        LOGGER.info(
            "event=resume_classified document_id=%s model_id=%s "
            "classification=%s confidence=%s decision=%s duration_ms=%s "
            "input_tokens=%s output_tokens=%s status=%s",
            document_id,
            self.settings.resume_processing_model_id,
            classification,
            value.confidence,
            decision,
            classified.invocation.duration_ms,
            classified.invocation.input_tokens,
            classified.invocation.output_tokens,
            status,
        )
        if status == DocumentStatus.REJECTED:
            LOGGER.info(
                "event=resume_rejected document_id=%s model_id=%s confidence=%s",
                document_id,
                self.settings.resume_processing_model_id,
                value.confidence,
            )
        elif status == DocumentStatus.NEEDS_REVIEW:
            LOGGER.info(
                "event=resume_needs_review document_id=%s model_id=%s confidence=%s",
                document_id,
                self.settings.resume_processing_model_id,
                value.confidence,
            )
        return status

    def _classification_decision(
        self,
        *,
        is_resume: bool,
        confidence: float,
    ) -> tuple[DocumentStatus, str, str]:
        if is_resume and confidence >= self.settings.resume_accept_confidence:
            return DocumentStatus.ACCEPTED, "ACCEPT", "resume"
        if confidence <= self.settings.resume_reject_low_confidence or (
            not is_resume
            and confidence >= self.settings.resume_not_resume_reject_confidence
        ):
            return DocumentStatus.REJECTED, "REJECT", "not_resume"
        return (
            DocumentStatus.NEEDS_REVIEW,
            "REVIEW",
            ("resume" if is_resume else "not_resume"),
        )

    def _extract_profile(
        self,
        *,
        document_id: UUID,
        attempt_started_at: datetime | None,
        document_text: str,
    ) -> DocumentStatus:
        LOGGER.info(
            "event=resume_extraction_started document_id=%s model_id=%s "
            "input_character_count=%s",
            document_id,
            self.settings.resume_processing_model_id,
            len(document_text),
        )
        try:
            extracted = self.extractor.extract(document_text)
        except BedrockTransientError as exc:
            self._release_for_retry(
                document_id=document_id,
                attempt_started_at=attempt_started_at,
                stable_status=DocumentStatus.ACCEPTED,
                error_code="BEDROCK_TRANSIENT",
            )
            raise PolicyTransientError("Bedrock extraction unavailable") from exc
        except BedrockPermanentError as exc:
            LOGGER.warning(
                "event=bedrock_permanent_error document_id=%s model_id=%s "
                "error_code=%s",
                document_id,
                self.settings.resume_processing_model_id,
                exc.code,
            )
            return self._mark_failed(
                document_id=document_id,
                attempt_started_at=attempt_started_at,
                code=f"BEDROCK_{exc.code}"[:100],
                message=exc.safe_message,
            )

        document = self._locked_owned(
            document_id=document_id,
            attempt_started_at=attempt_started_at,
            expected_status=DocumentStatus.ACCEPTED,
        )
        extracted_at = now_utc()
        draft = self.repository.get_draft_by_document(
            document_id=document_id,
            for_update=True,
        )
        created = draft is None
        if draft is None:
            context = document.context or {}
            draft = ResumeProfileDraft(
                document_id=document.id,
                tenant_id=document.tenant_id,
                source_app=document.source_app,
                profile_id=context.get("profile_id"),
                schema_version=SCHEMA_VERSION,
                payload=extracted.value.model_dump(mode="json"),
                model_id=self.settings.resume_processing_model_id,
                extracted_at=extracted_at,
            )
            self.repository.add_draft(draft)
        else:
            draft.schema_version = SCHEMA_VERSION
            draft.payload = extracted.value.model_dump(mode="json")
            draft.model_id = self.settings.resume_processing_model_id
            draft.extracted_at = extracted_at
        document.status = DocumentStatus.DATA_EXTRACTED
        self.repository.commit()
        LOGGER.info(
            "event=resume_extracted document_id=%s model_id=%s duration_ms=%s "
            "input_tokens=%s output_tokens=%s",
            document_id,
            self.settings.resume_processing_model_id,
            extracted.invocation.duration_ms,
            extracted.invocation.input_tokens,
            extracted.invocation.output_tokens,
        )
        LOGGER.info(
            "event=resume_profile_draft_created document_id=%s result_id=%s "
            "model_id=%s created=%s",
            document_id,
            draft.id,
            self.settings.resume_processing_model_id,
            created,
        )
        return self._complete(
            document_id=document_id,
            attempt_started_at=attempt_started_at,
        )

    def _complete(
        self,
        *,
        document_id: UUID,
        attempt_started_at: datetime | None,
    ) -> DocumentStatus:
        document = self._locked_owned(
            document_id=document_id,
            attempt_started_at=attempt_started_at,
            expected_status=DocumentStatus.DATA_EXTRACTED,
        )
        document.status = DocumentStatus.COMPLETED
        document.processing_started_at = None
        document.error_code = None
        document.error_message = None
        self.repository.commit()
        LOGGER.info(
            "event=resume_processing_completed document_id=%s model_id=%s status=%s",
            document_id,
            self.settings.resume_processing_model_id,
            DocumentStatus.COMPLETED,
        )
        return DocumentStatus.COMPLETED

    def _mark_failed(
        self,
        *,
        document_id: UUID,
        attempt_started_at: datetime | None,
        code: str,
        message: str,
    ) -> DocumentStatus:
        document = self.repository.get_for_processing(
            document_id=document_id,
            for_update=True,
        )
        if not self._owns_attempt(document, attempt_started_at):
            self.repository.rollback()
            raise PolicyTransientError("Resume processing claim changed")
        document.status = DocumentStatus.FAILED
        document.processing_started_at = None
        document.error_code = code
        document.error_message = message
        self.repository.commit()
        LOGGER.warning(
            "event=document_processing_failed_permanent document_id=%s "
            "model_id=%s error_code=%s status=%s",
            document_id,
            self.settings.resume_processing_model_id,
            code,
            DocumentStatus.FAILED,
        )
        return DocumentStatus.FAILED

    def _release_for_retry(
        self,
        *,
        document_id: UUID,
        attempt_started_at: datetime | None,
        stable_status: DocumentStatus,
        error_code: str,
    ) -> None:
        try:
            document = self.repository.get_for_processing(
                document_id=document_id,
                for_update=True,
            )
            if self._owns_attempt(document, attempt_started_at):
                document.status = stable_status
                document.processing_started_at = None
                self.repository.commit()
            else:
                self.repository.rollback()
        except SQLAlchemyError:
            self.repository.rollback()
        LOGGER.warning(
            "event=bedrock_transient_error document_id=%s model_id=%s error_code=%s",
            document_id,
            self.settings.resume_processing_model_id,
            error_code,
        )

    def _locked_owned(
        self,
        *,
        document_id: UUID,
        attempt_started_at: datetime | None,
        expected_status: DocumentStatus,
    ) -> Document:
        document = self.repository.get_for_processing(
            document_id=document_id,
            for_update=True,
        )
        if (
            not self._owns_attempt(document, attempt_started_at)
            or document.status != expected_status
        ):
            self.repository.rollback()
            raise PolicyTransientError("Resume processing claim changed")
        return document

    @staticmethod
    def _owns_attempt(
        document: Document | None,
        attempt_started_at: datetime | None,
    ) -> bool:
        return document is not None and _normalized_timestamp(
            document.processing_started_at
        ) == _normalized_timestamp(attempt_started_at)


def build_resume_processing_policy(
    *,
    repository: DocumentRepository,
    storage: DocumentStorage,
    settings: Settings,
) -> ResumeProcessingPolicy:
    client = BedrockStructuredClient(
        region_name=settings.resume_processing_bedrock_region,
        model_id=settings.resume_processing_model_id,
        connect_timeout_seconds=settings.resume_bedrock_connect_timeout_seconds,
        read_timeout_seconds=settings.resume_bedrock_read_timeout_seconds,
    )
    return ResumeProcessingPolicy(
        repository=repository,
        storage=storage,
        settings=settings,
        classifier=ResumeClassifier(client),
        extractor=ResumeExtractor(client),
        text_extractor=PdfTextExtractor(
            minimum_characters=settings.resume_min_extracted_characters,
            maximum_characters=settings.resume_max_model_input_characters,
        ),
    )
