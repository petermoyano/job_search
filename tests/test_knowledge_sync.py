from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.documents.models import Document, DocumentStatus, now_utc
from app.documents.repository import DocumentRepository
from app.knowledge.contracts import (
    CRANE_INTELLIGENCE_SOURCE_APP,
    KNOWLEDGE_BASE_PROCESSING_POLICY,
    KnowledgeSyncStatus,
)
from app.knowledge.ingestion import (
    KnowledgeIngestionJob,
    KnowledgeIngestionService,
)
from app.knowledge.sync import KnowledgeSyncReconciler


class FakeKnowledgeIngestionClient:
    def __init__(self, *, status: str, job_id: str = "ingestion-job") -> None:
        self.status = status
        self.job_id = job_id
        self.start_calls = 0
        self.get_calls = 0

    def start_ingestion_job(
        self,
        *,
        knowledge_base_id: str,
        data_source_id: str,
        client_token: str,
        description: str,
    ) -> str | None:
        self.start_calls += 1
        return self.job_id

    def get_ingestion_job(
        self,
        *,
        knowledge_base_id: str,
        data_source_id: str,
        ingestion_job_id: str,
    ) -> KnowledgeIngestionJob:
        self.get_calls += 1
        return KnowledgeIngestionJob(
            ingestion_job_id=ingestion_job_id,
            status=self.status,
            failure_reasons=("Synthetic Bedrock failure",)
            if self.status == "FAILED"
            else (),
        )


@pytest.fixture(autouse=True)
def knowledge_sync_test_environment() -> None:
    settings = get_settings()
    original_knowledge_base_id = settings.knowledge_base_id
    original_data_source_id = settings.knowledge_base_data_source_id
    settings.knowledge_base_id = "KB123"
    settings.knowledge_base_data_source_id = "DS123"
    assert engine.dialect.name == "sqlite"
    Base.metadata.create_all(bind=engine)
    Document.__table__.drop(bind=engine, checkfirst=True)
    Document.__table__.create(bind=engine)
    with SessionLocal() as session:
        session.execute(delete(Document))
        session.commit()
    yield
    settings.knowledge_base_id = original_knowledge_base_id
    settings.knowledge_base_data_source_id = original_data_source_id


def create_document(
    *,
    knowledge_sync_status: KnowledgeSyncStatus,
    ingestion_job_id: str | None,
) -> UUID:
    document_id = uuid4()
    document = Document(
        id=document_id,
        tenant_id="creactis",
        project_id="project-1",
        source_app=CRANE_INTELLIGENCE_SOURCE_APP,
        processing_policy=KNOWLEDGE_BASE_PROCESSING_POLICY,
        context={
            "knowledge": {
                "asset_id": "crane-1",
                "document_type": "manual",
                "language": "es",
            }
        },
        original_filename="manual.pdf",
        mime_type="application/pdf",
        file_size_bytes=256,
        sha256="a" * 64,
        s3_bucket="test-documents",
        s3_key=f"documents/creactis/crane-intelligence/project-1/{document_id}/manual.pdf",
        status=DocumentStatus.PREPROCESSED,
        preprocessed_at=now_utc(),
        knowledge_sync_status=knowledge_sync_status,
        knowledge_ingestion_job_id=ingestion_job_id,
        knowledge_sync_requested_at=now_utc(),
    )
    with SessionLocal() as session:
        session.add(document)
        session.commit()
    return document_id


def load_document(document_id: UUID) -> Document:
    with SessionLocal() as session:
        document = session.get(Document, document_id)
        assert document is not None
        session.expunge(document)
        return document


def reconcile(client: FakeKnowledgeIngestionClient):
    with SessionLocal() as session:
        service = KnowledgeIngestionService(
            settings=get_settings(),
            client=client,
        )
        return KnowledgeSyncReconciler(
            repository=DocumentRepository(session),
            ingestion_service=service,
        ).reconcile()


def test_complete_ingestion_marks_document_as_rag_indexed() -> None:
    document_id = create_document(
        knowledge_sync_status=KnowledgeSyncStatus.IN_PROGRESS,
        ingestion_job_id="job-complete",
    )
    client = FakeKnowledgeIngestionClient(status="COMPLETE")

    summary = reconcile(client)

    document = load_document(document_id)
    assert summary.completed == 1
    assert client.get_calls == 1
    assert document.status == DocumentStatus.RAG_INDEXED
    assert document.knowledge_sync_status == KnowledgeSyncStatus.COMPLETE
    assert document.knowledge_sync_completed_at is not None


def test_pending_ingestion_is_retried_idempotently() -> None:
    document_id = create_document(
        knowledge_sync_status=KnowledgeSyncStatus.PENDING,
        ingestion_job_id=None,
    )
    client = FakeKnowledgeIngestionClient(status="STARTING", job_id="job-retry")

    summary = reconcile(client)

    document = load_document(document_id)
    assert summary.started == 1
    assert client.start_calls == 1
    assert client.get_calls == 0
    assert document.status == DocumentStatus.PREPROCESSED
    assert document.knowledge_sync_status == KnowledgeSyncStatus.IN_PROGRESS
    assert document.knowledge_ingestion_job_id == "job-retry"


def test_failed_ingestion_keeps_document_out_of_retrieval() -> None:
    document_id = create_document(
        knowledge_sync_status=KnowledgeSyncStatus.IN_PROGRESS,
        ingestion_job_id="job-failed",
    )
    client = FakeKnowledgeIngestionClient(status="FAILED")

    summary = reconcile(client)

    document = load_document(document_id)
    assert summary.failed == 1
    assert document.status == DocumentStatus.PREPROCESSED
    assert document.knowledge_sync_status == KnowledgeSyncStatus.FAILED
    assert document.error_code == "KNOWLEDGE_INGESTION_FAILED"
    assert document.error_message == "Synthetic Bedrock failure"
