from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
import json
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.documents import worker
from app.documents.models import Document, DocumentStatus, now_utc
from app.documents.processing import (
    DocumentProcessingService,
    ProcessingOutcome,
    TransientProcessingError,
)
from app.documents.repository import DocumentRepository
from app.documents.storage import (
    StorageUnavailableError,
    StoredObjectContent,
)
from app.knowledge.contracts import KnowledgeSyncStatus
from app.knowledge.ingestion import KnowledgeIngestionService


VALID_PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


class ProcessingStorage:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], StoredObjectContent] = {}
        self.transient_keys: set[tuple[str, str]] = set()
        self.read_count = 0

    def read_object(self, *, bucket: str, key: str) -> StoredObjectContent:
        self.read_count += 1
        if (bucket, key) in self.transient_keys:
            raise StorageUnavailableError("temporary S3 failure")
        return self.objects[(bucket, key)]

    def write_object(
        self,
        *,
        bucket: str,
        key: str,
        body: bytes,
        content_type: str,
    ) -> None:
        self.objects[(bucket, key)] = StoredObjectContent(
            size_bytes=len(body),
            metadata={},
            body=body,
        )


class FakeKnowledgeIngestionClient:
    def __init__(self, *, job_id: str | None = "ABCDEFGHIJ") -> None:
        self.job_id = job_id
        self.calls: list[dict[str, str]] = []

    def start_ingestion_job(
        self,
        *,
        knowledge_base_id: str,
        data_source_id: str,
        client_token: str,
        description: str,
    ) -> str | None:
        self.calls.append(
            {
                "knowledge_base_id": knowledge_base_id,
                "data_source_id": data_source_id,
                "client_token": client_token,
                "description": description,
            }
        )
        return self.job_id


@pytest.fixture(autouse=True)
def processing_test_environment() -> None:
    settings = get_settings()
    original_max_size = settings.documents_max_file_size_bytes
    original_lease = settings.document_processing_lease_seconds
    settings.documents_max_file_size_bytes = 20 * 1024 * 1024
    settings.document_processing_lease_seconds = 300
    assert engine.dialect.name == "sqlite"
    Base.metadata.create_all(bind=engine)
    Document.__table__.drop(bind=engine, checkfirst=True)
    Document.__table__.create(bind=engine)
    with SessionLocal() as session:
        session.execute(delete(Document))
        session.commit()
    yield
    settings.documents_max_file_size_bytes = original_max_size
    settings.document_processing_lease_seconds = original_lease


def create_document(
    *,
    storage: ProcessingStorage,
    body: bytes = VALID_PDF,
    status: DocumentStatus = DocumentStatus.UPLOADED,
    tenant_id: str = "authoritative-tenant",
    source_app: str = "job-search",
) -> UUID:
    document_id = uuid4()
    bucket = "test-documents-bucket"
    key = f"documents/{tenant_id}/{source_app}/default/{document_id}/original.pdf"
    document = Document(
        id=document_id,
        tenant_id=tenant_id,
        project_id=None,
        source_app=source_app,
        processing_policy="test",
        original_filename="synthetic.pdf",
        mime_type="application/pdf",
        file_size_bytes=len(body),
        s3_bucket=bucket,
        s3_key=key,
        status=status,
        uploaded_at=now_utc(),
        processing_enqueued_at=now_utc(),
    )
    with SessionLocal() as session:
        session.add(document)
        session.commit()
    storage.objects[(bucket, key)] = StoredObjectContent(
        size_bytes=len(body),
        metadata={"document-id": str(document_id)},
        body=body,
    )
    return document_id


def process_document(*, document_id: UUID, storage: ProcessingStorage):
    with SessionLocal() as session:
        return DocumentProcessingService(
            repository=DocumentRepository(session),
            storage=storage,
            settings=get_settings(),
        ).process(document_id=document_id)


def load_document(document_id: UUID) -> Document:
    with SessionLocal() as session:
        document = session.get(Document, document_id)
        assert document is not None
        session.expunge(document)
        return document


def test_valid_pdf_becomes_preprocessed_and_persists_sha256() -> None:
    storage = ProcessingStorage()
    document_id = create_document(storage=storage)

    result = process_document(document_id=document_id, storage=storage)

    document = load_document(document_id)
    assert result.outcome == ProcessingOutcome.PREPROCESSED
    assert document.status == DocumentStatus.PREPROCESSED
    assert document.sha256 == sha256(VALID_PDF).hexdigest()
    assert document.preprocessed_at is not None
    assert document.processing_started_at is None


def test_invalid_pdf_signature_becomes_failed() -> None:
    storage = ProcessingStorage()
    document_id = create_document(storage=storage, body=b"not-a-real-pdf")

    result = process_document(document_id=document_id, storage=storage)

    document = load_document(document_id)
    assert result.status == DocumentStatus.FAILED
    assert document.status == DocumentStatus.FAILED
    assert document.error_code == "INVALID_PDF_SIGNATURE"
    assert document.sha256 is None


def test_missing_document_is_handled_safely() -> None:
    result = process_document(
        document_id=uuid4(),
        storage=ProcessingStorage(),
    )

    assert result.outcome == ProcessingOutcome.NOT_FOUND


def test_already_preprocessed_document_is_skipped() -> None:
    storage = ProcessingStorage()
    document_id = create_document(
        storage=storage,
        status=DocumentStatus.PREPROCESSED,
    )

    result = process_document(document_id=document_id, storage=storage)

    assert result.outcome == ProcessingOutcome.SKIPPED
    assert storage.read_count == 0


def test_duplicate_message_is_idempotent() -> None:
    storage = ProcessingStorage()
    document_id = create_document(storage=storage)

    first = process_document(document_id=document_id, storage=storage)
    second = process_document(document_id=document_id, storage=storage)

    assert first.outcome == ProcessingOutcome.PREPROCESSED
    assert second.outcome == ProcessingOutcome.SKIPPED
    assert storage.read_count == 1


def test_transient_s3_failure_releases_document_for_retry() -> None:
    storage = ProcessingStorage()
    document_id = create_document(storage=storage)
    document = load_document(document_id)
    storage.transient_keys.add((document.s3_bucket, document.s3_key))

    with pytest.raises(TransientProcessingError):
        process_document(document_id=document_id, storage=storage)

    document = load_document(document_id)
    assert document.status == DocumentStatus.UPLOADED
    assert document.processing_started_at is None
    assert document.error_code is None


def test_permanent_failure_is_not_reprocessed() -> None:
    storage = ProcessingStorage()
    document_id = create_document(storage=storage, body=b"invalid")

    first = process_document(document_id=document_id, storage=storage)
    second = process_document(document_id=document_id, storage=storage)

    assert first.status == DocumentStatus.FAILED
    assert second.outcome == ProcessingOutcome.SKIPPED
    assert storage.read_count == 1


def test_stale_processing_lease_can_be_reclaimed() -> None:
    storage = ProcessingStorage()
    document_id = create_document(
        storage=storage,
        status=DocumentStatus.PROCESSING,
    )
    with SessionLocal() as session:
        document = session.get(Document, document_id)
        assert document is not None
        document.processing_started_at = now_utc() - timedelta(minutes=10)
        session.commit()

    result = process_document(document_id=document_id, storage=storage)

    assert result.outcome == ProcessingOutcome.PREPROCESSED


def test_worker_returns_only_transient_records_as_batch_failures(monkeypatch) -> None:
    storage = ProcessingStorage()
    valid_id = create_document(storage=storage, tenant_id="db-tenant-one")
    transient_id = create_document(storage=storage, tenant_id="db-tenant-two")
    transient_document = load_document(transient_id)
    storage.transient_keys.add(
        (transient_document.s3_bucket, transient_document.s3_key)
    )
    monkeypatch.setattr(worker, "get_document_storage", lambda: storage)

    response = worker.handler(
        {
            "Records": [
                {
                    "messageId": "valid-message",
                    "body": json.dumps({"version": 1, "document_id": str(valid_id)}),
                },
                {
                    "messageId": "transient-message",
                    "body": json.dumps(
                        {"version": 1, "document_id": str(transient_id)}
                    ),
                },
            ]
        },
        None,
    )

    assert response == {"batchItemFailures": [{"itemIdentifier": "transient-message"}]}
    assert load_document(valid_id).status == DocumentStatus.PREPROCESSED
    assert load_document(transient_id).status == DocumentStatus.UPLOADED


def test_worker_rejects_tenant_metadata_in_message(monkeypatch) -> None:
    storage = ProcessingStorage()
    document_id = create_document(storage=storage, tenant_id="database-tenant")
    monkeypatch.setattr(worker, "get_document_storage", lambda: storage)

    response = worker.handler(
        {
            "Records": [
                {
                    "messageId": "untrusted-metadata",
                    "body": json.dumps(
                        {
                            "version": 1,
                            "document_id": str(document_id),
                            "tenant_id": "attacker-tenant",
                        }
                    ),
                }
            ]
        },
        None,
    )

    assert response == {"batchItemFailures": []}
    assert load_document(document_id).status == DocumentStatus.UPLOADED
    assert storage.read_count == 0


def _make_knowledge_document(
    *,
    storage: ProcessingStorage,
) -> UUID:
    document_id = create_document(
        storage=storage,
        tenant_id="creactis",
        source_app="crane-intelligence",
    )
    with SessionLocal() as session:
        document = session.get(Document, document_id)
        assert document is not None
        document.project_id = "crane-demo"
        document.processing_policy = "knowledge-base"
        document.context = {
            "knowledge": {
                "asset_id": "crane-151",
                "component_id": "hoist",
                "document_type": "maintenance-procedure",
                "document_title": "Manual de mantenimiento",
                "language": "es",
            }
        }
        session.commit()
    return document_id


def test_knowledge_document_writes_sidecar_and_tracks_ingestion_job() -> None:
    storage = ProcessingStorage()
    document_id = _make_knowledge_document(storage=storage)
    settings = get_settings()
    original_knowledge_base_id = settings.knowledge_base_id
    original_data_source_id = settings.knowledge_base_data_source_id
    settings.knowledge_base_id = "KBABCDEFGHI"
    settings.knowledge_base_data_source_id = "DSABCDEFGHI"
    client = FakeKnowledgeIngestionClient()
    try:
        with SessionLocal() as session:
            result = DocumentProcessingService(
                repository=DocumentRepository(session),
                storage=storage,
                settings=settings,
                knowledge_ingestion_service=KnowledgeIngestionService(
                    storage=storage,
                    settings=settings,
                    client=client,
                ),
            ).process(document_id=document_id)
    finally:
        settings.knowledge_base_id = original_knowledge_base_id
        settings.knowledge_base_data_source_id = original_data_source_id

    document = load_document(document_id)
    sidecar_key = f"{document.s3_key}.metadata.json"
    sidecar = json.loads(storage.objects[(document.s3_bucket, sidecar_key)].body)

    assert result.status == DocumentStatus.PREPROCESSED
    assert document.knowledge_sync_status == KnowledgeSyncStatus.IN_PROGRESS
    assert document.knowledge_ingestion_job_id == "ABCDEFGHIJ"
    assert document.knowledge_sync_requested_at is not None
    assert sidecar == {
        "metadataAttributes": {
            "document_id": str(document_id),
            "tenant_id": "creactis",
            "source_app": "crane-intelligence",
            "project_id": "crane-demo",
            "asset_id": "crane-151",
            "component_id": "hoist",
            "document_type": "maintenance-procedure",
            "document_title": "Manual de mantenimiento",
            "language": "es",
            "sha256": sha256(VALID_PDF).hexdigest(),
        }
    }
    assert client.calls[0]["knowledge_base_id"] == "KBABCDEFGHI"
    assert client.calls[0]["data_source_id"] == "DSABCDEFGHI"
    assert len(client.calls[0]["client_token"]) >= 33


def test_knowledge_document_records_pending_when_ingestion_is_already_running() -> None:
    storage = ProcessingStorage()
    document_id = _make_knowledge_document(storage=storage)
    settings = get_settings()
    original_knowledge_base_id = settings.knowledge_base_id
    original_data_source_id = settings.knowledge_base_data_source_id
    settings.knowledge_base_id = "KBABCDEFGHI"
    settings.knowledge_base_data_source_id = "DSABCDEFGHI"
    try:
        with SessionLocal() as session:
            DocumentProcessingService(
                repository=DocumentRepository(session),
                storage=storage,
                settings=settings,
                knowledge_ingestion_service=KnowledgeIngestionService(
                    storage=storage,
                    settings=settings,
                    client=FakeKnowledgeIngestionClient(job_id=None),
                ),
            ).process(document_id=document_id)
    finally:
        settings.knowledge_base_id = original_knowledge_base_id
        settings.knowledge_base_data_source_id = original_data_source_id

    document = load_document(document_id)
    assert document.status == DocumentStatus.PREPROCESSED
    assert document.knowledge_sync_status == KnowledgeSyncStatus.PENDING
    assert document.knowledge_ingestion_job_id is None
