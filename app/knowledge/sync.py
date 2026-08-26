from __future__ import annotations

from dataclasses import asdict, dataclass
import logging
from typing import Final

from app.documents.models import Document, DocumentStatus, now_utc
from app.documents.repository import DocumentRepository
from app.knowledge.contracts import KnowledgeSyncStatus
from app.knowledge.ingestion import (
    KnowledgeIngestionPermanentError,
    KnowledgeIngestionService,
    KnowledgeIngestionTransientError,
)


LOGGER = logging.getLogger(__name__)

BEDROCK_COMPLETE: Final = "COMPLETE"
BEDROCK_TERMINAL_FAILURES: Final = frozenset({"FAILED", "STOPPED"})


@dataclass
class KnowledgeSyncSummary:
    checked: int = 0
    started: int = 0
    completed: int = 0
    failed: int = 0
    deferred: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


class KnowledgeSyncReconciler:
    def __init__(
        self,
        *,
        repository: DocumentRepository,
        ingestion_service: KnowledgeIngestionService,
    ) -> None:
        self.repository = repository
        self.ingestion_service = ingestion_service

    def reconcile(self, *, limit: int = 25) -> KnowledgeSyncSummary:
        summary = KnowledgeSyncSummary()
        candidates = self.repository.list_knowledge_sync_candidates(limit=limit)

        for candidate in candidates:
            document = self.repository.get_for_processing(
                document_id=candidate.id,
                for_update=True,
            )
            if not self._is_candidate(document):
                self.repository.commit()
                continue

            summary.checked += 1
            try:
                self._reconcile_document(document, summary)
                self.repository.commit()
            except KnowledgeIngestionPermanentError as exc:
                self._mark_failed(document, code=exc.code, message=exc.safe_message)
                self.repository.commit()
                summary.failed += 1
            except KnowledgeIngestionTransientError:
                self.repository.rollback()
                summary.deferred += 1
                LOGGER.warning(
                    "event=knowledge_sync_deferred document_id=%s",
                    document.id,
                    exc_info=True,
                )

        return summary

    def _reconcile_document(
        self,
        document: Document,
        summary: KnowledgeSyncSummary,
    ) -> None:
        if (
            document.knowledge_sync_status == KnowledgeSyncStatus.PENDING
            or not document.knowledge_ingestion_job_id
        ):
            request = self.ingestion_service.retry_pending_sync(document=document)
            document.knowledge_sync_status = request.status
            document.knowledge_ingestion_job_id = request.ingestion_job_id
            document.knowledge_sync_requested_at = request.requested_at
            if request.status == KnowledgeSyncStatus.IN_PROGRESS:
                summary.started += 1
            else:
                summary.deferred += 1
            return

        job = self.ingestion_service.get_ingestion_job(
            ingestion_job_id=document.knowledge_ingestion_job_id
        )
        if job.status == BEDROCK_COMPLETE:
            document.status = DocumentStatus.RAG_INDEXED
            document.knowledge_sync_status = KnowledgeSyncStatus.COMPLETE
            document.knowledge_sync_completed_at = now_utc()
            document.error_code = None
            document.error_message = None
            summary.completed += 1
            return

        if job.status in BEDROCK_TERMINAL_FAILURES:
            message = "; ".join(job.failure_reasons) or (
                "Bedrock Knowledge Base ingestion did not complete"
            )
            self._mark_failed(
                document,
                code=f"KNOWLEDGE_INGESTION_{job.status}",
                message=message,
            )
            summary.failed += 1
            return

        summary.deferred += 1

    @staticmethod
    def _is_candidate(document: Document | None) -> bool:
        return (
            document is not None
            and document.status == DocumentStatus.PREPROCESSED
            and document.knowledge_sync_status
            in {KnowledgeSyncStatus.PENDING, KnowledgeSyncStatus.IN_PROGRESS}
        )

    @staticmethod
    def _mark_failed(document: Document, *, code: str, message: str) -> None:
        document.knowledge_sync_status = KnowledgeSyncStatus.FAILED
        document.knowledge_sync_completed_at = now_utc()
        document.error_code = code[:100]
        document.error_message = message
