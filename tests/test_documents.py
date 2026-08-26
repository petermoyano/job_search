from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import delete

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.documents.auth import AuthContext, credential_store
from app.documents.models import (
    Document,
    DocumentStatus,
    ResumeProfileDraft,
    now_utc,
)
from app.documents.queue import (
    QueueUnavailableError,
    SqsDocumentProcessingQueue,
    get_document_processing_queue,
)
from app.documents.repository import DocumentRepository
from app.documents.schemas import UploadUrlRequest
from app.documents.service import DocumentService, build_s3_key
from app.knowledge.contracts import (
    KNOWLEDGE_BASE_PROCESSING_POLICY,
    KnowledgeRetrieveRequest,
)
from app.documents.storage import (
    ObjectNotFoundError,
    PresignedUpload,
    S3DocumentStorage,
    StoredObject,
    get_document_storage,
)
from app.main import app


JOB_SECRET = "test-job-search-secret"
CRANE_SECRET = "test-crane-secret"
JOB_HEADERS = {"Authorization": f"Bearer {JOB_SECRET}"}
CRANE_HEADERS = {"Authorization": f"Bearer {CRANE_SECRET}"}


class FakeQueue:
    def __init__(self) -> None:
        self.document_ids: list[UUID] = []
        self.fail = False

    def enqueue(self, *, document_id: UUID) -> None:
        if self.fail:
            raise QueueUnavailableError("queue unavailable")
        self.document_ids.append(document_id)


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], StoredObject] = {}
        self.last_bucket: str | None = None
        self.last_key: str | None = None

    def create_upload_url(
        self,
        *,
        bucket: str,
        key: str,
        document_id: UUID,
        file_size_bytes: int,
        expires_in: int,
    ) -> PresignedUpload:
        self.last_bucket = bucket
        self.last_key = key
        return PresignedUpload(
            url=f"https://uploads.example/{document_id}?expires={expires_in}",
            required_headers={
                "Content-Type": "application/pdf",
                "x-amz-meta-document-id": str(document_id),
            },
        )

    def head_object(self, *, bucket: str, key: str) -> StoredObject:
        try:
            return self.objects[(bucket, key)]
        except KeyError as exc:
            raise ObjectNotFoundError(key) from exc


@pytest.fixture(autouse=True)
def document_test_environment() -> FakeStorage:
    settings = get_settings()
    original_values = {
        "documents_s3_bucket": settings.documents_s3_bucket,
        "documents_max_file_size_bytes": settings.documents_max_file_size_bytes,
        "documents_upload_url_expires_seconds": (
            settings.documents_upload_url_expires_seconds
        ),
        "document_client_keys_json": settings.document_client_keys_json,
    }
    settings.documents_s3_bucket = "test-documents-bucket"
    settings.documents_max_file_size_bytes = 20 * 1024 * 1024
    settings.documents_upload_url_expires_seconds = 900
    settings.document_client_keys_json = (
        '{"test-job-search-secret":{"source_app":"job-search",'
        '"tenant_ids":["job-search"]},'
        '"test-crane-secret":{"source_app":"crane-intelligence",'
        '"tenant_ids":["creactis"]}}'
    )
    credential_store.clear_cache()

    assert engine.dialect.name == "sqlite"
    Base.metadata.create_all(bind=engine)
    Document.__table__.drop(bind=engine, checkfirst=True)
    Document.__table__.create(bind=engine)
    with SessionLocal() as session:
        session.execute(delete(Document))
        session.commit()

    storage = FakeStorage()
    processing_queue = FakeQueue()
    storage.processing_queue = processing_queue
    app.dependency_overrides[get_document_storage] = lambda: storage
    app.dependency_overrides[get_document_processing_queue] = lambda: processing_queue
    yield storage

    app.dependency_overrides.pop(get_document_storage, None)
    app.dependency_overrides.pop(get_document_processing_queue, None)
    credential_store.clear_cache()
    for name, value in original_values.items():
        setattr(settings, name, value)


def valid_payload(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "tenant_id": "job-search",
        "project_id": None,
        "source_app": "job-search",
        "processing_policy": "cv",
        "filename": "candidate.pdf",
        "mime_type": "application/pdf",
        "file_size_bytes": 128,
    }
    payload.update(updates)
    return payload



def test_valid_knowledge_base_upload_request() -> None:
    request = UploadUrlRequest.model_validate(
        valid_payload(
            tenant_id="creactis",
            project_id="crane-demo",
            source_app="crane-intelligence",
            processing_policy=KNOWLEDGE_BASE_PROCESSING_POLICY,
            context={
                "knowledge": {
                    "asset_id": "CRN-01",
                    "component_id": "hoist",
                    "document_type": "manual",
                    "document_title": "FORVIS FVS3 manual",
                    "language": "es",
                }
            },
        )
    )

    assert request.context is not None
    assert request.context.knowledge is not None
    assert request.context.knowledge.asset_id == "CRN-01"


@pytest.mark.parametrize(
    "updates",
    [
        {
            "source_app": "job-search",
            "project_id": "crane-demo",
            "processing_policy": KNOWLEDGE_BASE_PROCESSING_POLICY,
            "context": {
                "knowledge": {
                    "asset_id": "CRN-01",
                    "document_type": "manual",
                }
            },
        },
        {
            "tenant_id": "creactis",
            "source_app": "crane-intelligence",
            "processing_policy": KNOWLEDGE_BASE_PROCESSING_POLICY,
            "context": {
                "knowledge": {
                    "asset_id": "CRN-01",
                    "document_type": "manual",
                }
            },
        },
        {
            "tenant_id": "creactis",
            "project_id": "crane-demo",
            "source_app": "crane-intelligence",
            "processing_policy": KNOWLEDGE_BASE_PROCESSING_POLICY,
        },
    ],
)
def test_knowledge_base_upload_requires_its_scope_and_metadata(
    updates: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        UploadUrlRequest.model_validate(valid_payload(**updates))


def test_knowledge_context_requires_knowledge_base_policy() -> None:
    with pytest.raises(ValidationError):
        UploadUrlRequest.model_validate(
            valid_payload(
                context={
                    "knowledge": {
                        "asset_id": "CRN-01",
                        "document_type": "manual",
                    }
                }
            )
        )


def test_knowledge_retrieve_contract_normalizes_query() -> None:
    request = KnowledgeRetrieveRequest.model_validate(
        {
            "query": "  What manual  describes   the hoist? ",
            "asset_id": "CRN-01",
            "component_id": "hoist",
        }
    )

    assert request.query == "What manual describes the hoist?"
    assert request.max_results == 5


def test_valid_pdf_request() -> None:
    request = UploadUrlRequest.model_validate(valid_payload())
    assert request.mime_type == "application/pdf"
    assert request.filename == "candidate.pdf"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("mime_type", "text/plain"),
        ("filename", "candidate.txt"),
    ],
)
def test_invalid_pdf_request(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        UploadUrlRequest.model_validate(valid_payload(**{field: value}))


def test_s3_key_does_not_use_original_filename() -> None:
    document_id = uuid4()
    key = build_s3_key(
        tenant_id="creactis",
        source_app="crane-intelligence",
        project_id="halliburton-demo",
        document_id=document_id,
    )
    assert key == (
        "documents/creactis/crane-intelligence/halliburton-demo/"
        f"{document_id}/original.pdf"
    )


def test_s3_storage_uses_regional_endpoint_and_signed_constraints(
    monkeypatch,
) -> None:
    captured_client_options: dict[str, object] = {}
    captured_presign: dict[str, object] = {}

    class RecordingClient:
        def generate_presigned_url(self, operation, **kwargs):
            captured_presign["operation"] = operation
            captured_presign.update(kwargs)
            return "https://regional-upload.example/signed"

    def fake_client(service_name: str, **kwargs):
        captured_client_options["service_name"] = service_name
        captured_client_options.update(kwargs)
        return RecordingClient()

    monkeypatch.setattr("boto3.client", fake_client)
    storage = S3DocumentStorage(region_name="sa-east-1")
    document_id = uuid4()
    storage.create_upload_url(
        bucket="private-bucket",
        key=f"documents/example/{document_id}/original.pdf",
        document_id=document_id,
        file_size_bytes=321,
        expires_in=900,
    )

    assert captured_client_options["endpoint_url"] == (
        "https://s3.sa-east-1.amazonaws.com"
    )
    params = captured_presign["Params"]
    assert params["ContentType"] == "application/pdf"
    assert params["ContentLength"] == 321
    assert params["Metadata"] == {"document-id": str(document_id)}


def test_service_creates_pending_document(
    document_test_environment: FakeStorage,
) -> None:
    settings = get_settings()
    with SessionLocal() as session:
        service = DocumentService(
            repository=DocumentRepository(session),
            storage=document_test_environment,
            processing_queue=document_test_environment.processing_queue,
            settings=settings,
        )
        result = service.create_upload(
            payload=UploadUrlRequest.model_validate(valid_payload()),
            auth_context=AuthContext(
                source_app="job-search", tenant_ids=frozenset({"job-search"})
            ),
        )
        assert result.document.status == DocumentStatus.PENDING_UPLOAD
        assert result.document.s3_key.endswith(f"/{result.document.id}/original.pdf")
        assert result.upload.required_headers["Content-Type"] == "application/pdf"


def test_upload_url_rejects_file_over_configured_limit() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/documents/upload-url",
            headers=JOB_HEADERS,
            json=valid_payload(file_size_bytes=20 * 1024 * 1024 + 1),
        )
    assert response.status_code == 413


def test_upload_url_api_creates_document() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/documents/upload-url", headers=JOB_HEADERS, json=valid_payload()
        )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "PENDING_UPLOAD"
    assert body["expires_in"] == 900
    assert body["required_headers"]["Content-Type"] == "application/pdf"
    assert "upload_url" in body


def test_documents_api_requires_authentication() -> None:
    with TestClient(app) as client:
        response = client.post("/documents/upload-url", json=valid_payload())
    assert response.status_code == 401


@pytest.mark.parametrize(
    "payload",
    [
        valid_payload(source_app="crane-intelligence"),
        valid_payload(tenant_id="creactis"),
    ],
)
def test_client_cannot_create_outside_its_scope(payload: dict[str, object]) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/documents/upload-url", headers=JOB_HEADERS, json=payload
        )
    assert response.status_code == 403


def test_complete_upload_and_get_status(
    document_test_environment: FakeStorage,
) -> None:
    with TestClient(app) as client:
        created = client.post(
            "/documents/upload-url", headers=JOB_HEADERS, json=valid_payload()
        )
        document_id = created.json()["document_id"]
        assert document_test_environment.last_bucket is not None
        assert document_test_environment.last_key is not None
        document_test_environment.objects[
            (
                document_test_environment.last_bucket,
                document_test_environment.last_key,
            )
        ] = StoredObject(
            size_bytes=128,
            content_type="application/pdf",
            metadata={"document-id": document_id},
        )

        completed = client.post(
            f"/documents/{document_id}/complete-upload",
            headers=JOB_HEADERS,
        )
        loaded = client.get(
            f"/documents/{document_id}",
            headers=JOB_HEADERS,
        )

    assert completed.status_code == 200
    assert completed.json()["status"] == "UPLOADED"
    assert completed.json()["uploaded_at"] is not None
    assert loaded.status_code == 200
    assert loaded.json()["filename"] == "candidate.pdf"
    assert loaded.json()["status"] == "UPLOADED"
    assert "s3_bucket" not in loaded.json()
    assert "s3_key" not in loaded.json()


def test_complete_upload_rejects_missing_object() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/documents/upload-url", headers=JOB_HEADERS, json=valid_payload()
        )
        document_id = created.json()["document_id"]
        completed = client.post(
            f"/documents/{document_id}/complete-upload",
            headers=JOB_HEADERS,
        )
        loaded = client.get(f"/documents/{document_id}", headers=JOB_HEADERS)

    assert completed.status_code == 409
    assert loaded.json()["status"] == "PENDING_UPLOAD"


def test_get_hides_documents_from_other_client() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/documents/upload-url", headers=JOB_HEADERS, json=valid_payload()
        )
        response = client.get(
            f"/documents/{created.json()['document_id']}",
            headers=CRANE_HEADERS,
        )
    assert response.status_code == 404


def test_get_unknown_document_returns_not_found() -> None:
    with TestClient(app) as client:
        response = client.get(
            f"/documents/{uuid4()}",
            headers=JOB_HEADERS,
        )
    assert response.status_code == 404


def test_sqs_queue_publishes_minimal_versioned_message(monkeypatch) -> None:
    sent: dict[str, str] = {}

    class RecordingSqsClient:
        def send_message(self, **kwargs) -> None:
            sent.update(kwargs)

    monkeypatch.setattr(
        "boto3.client",
        lambda service_name, **_kwargs: RecordingSqsClient(),
    )
    queue = SqsDocumentProcessingQueue(
        queue_url="https://sqs.example/processing",
        region_name="sa-east-1",
    )
    document_id = uuid4()

    queue.enqueue(document_id=document_id)

    assert sent["QueueUrl"] == "https://sqs.example/processing"
    assert json.loads(sent["MessageBody"]) == {
        "version": 1,
        "document_id": str(document_id),
    }


def test_complete_upload_enqueues_only_once(
    document_test_environment: FakeStorage,
) -> None:
    with TestClient(app) as client:
        created = client.post(
            "/documents/upload-url",
            headers=JOB_HEADERS,
            json=valid_payload(),
        )
        document_id = created.json()["document_id"]
        document_test_environment.objects[
            (
                document_test_environment.last_bucket,
                document_test_environment.last_key,
            )
        ] = StoredObject(
            size_bytes=128,
            content_type="application/pdf",
            metadata={"document-id": document_id},
        )

        first = client.post(
            f"/documents/{document_id}/complete-upload",
            headers=JOB_HEADERS,
        )
        second = client.post(
            f"/documents/{document_id}/complete-upload",
            headers=JOB_HEADERS,
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert document_test_environment.processing_queue.document_ids == [
        UUID(document_id)
    ]


def test_queue_failure_rolls_back_verified_completion(
    document_test_environment: FakeStorage,
) -> None:
    with TestClient(app) as client:
        created = client.post(
            "/documents/upload-url",
            headers=JOB_HEADERS,
            json=valid_payload(),
        )
        document_id = created.json()["document_id"]
        document_test_environment.objects[
            (
                document_test_environment.last_bucket,
                document_test_environment.last_key,
            )
        ] = StoredObject(
            size_bytes=128,
            content_type="application/pdf",
            metadata={"document-id": document_id},
        )
        document_test_environment.processing_queue.fail = True

        completed = client.post(
            f"/documents/{document_id}/complete-upload",
            headers=JOB_HEADERS,
        )
        loaded = client.get(
            f"/documents/{document_id}",
            headers=JOB_HEADERS,
        )

    assert completed.status_code == 503
    assert loaded.status_code == 200
    assert loaded.json()["status"] == "PENDING_UPLOAD"
    assert document_test_environment.processing_queue.document_ids == []


def test_resume_upload_accepts_valid_profile_context() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/documents/upload-url",
            headers=JOB_HEADERS,
            json=valid_payload(
                processing_policy="resume",
                context={"profile_id": "peter"},
            ),
        )

    assert response.status_code == 201
    with SessionLocal() as session:
        document = session.get(Document, UUID(response.json()["document_id"]))
        assert document is not None
        assert document.context == {"profile_id": "peter"}


def test_resume_policy_is_rejected_for_other_source_app() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/documents/upload-url",
            headers=CRANE_HEADERS,
            json=valid_payload(
                tenant_id="creactis",
                source_app="crane-intelligence",
                processing_policy="resume",
            ),
        )

    assert response.status_code == 422


def test_document_result_is_tenant_scoped_and_reported_on_document() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/documents/upload-url",
            headers=JOB_HEADERS,
            json=valid_payload(
                processing_policy="resume",
                context={"profile_id": "peter"},
            ),
        )
        document_id = UUID(created.json()["document_id"])
        with SessionLocal() as session:
            draft = ResumeProfileDraft(
                document_id=document_id,
                tenant_id="job-search",
                source_app="job-search",
                profile_id="peter",
                schema_version="resume_profile_draft_v1",
                payload={},
                model_id="mistral.ministral-3-14b-instruct",
                extracted_at=now_utc(),
            )
            session.add(draft)
            session.commit()
            result_id = str(draft.id)

        document_response = client.get(
            f"/documents/{document_id}",
            headers=JOB_HEADERS,
        )
        result_response = client.get(
            f"/documents/{document_id}/result",
            headers=JOB_HEADERS,
        )
        denied_response = client.get(
            f"/documents/{document_id}/result",
            headers=CRANE_HEADERS,
        )

    assert document_response.status_code == 200
    assert document_response.json()["result_type"] == "resume_profile_draft"
    assert document_response.json()["result_id"] == result_id
    assert result_response.status_code == 200
    assert result_response.json()["id"] == result_id
    assert result_response.json()["profile_id"] == "peter"
    assert result_response.json()["payload"]["skills"] == []
    assert denied_response.status_code == 404


def test_document_result_returns_not_found_before_extraction() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/documents/upload-url",
            headers=JOB_HEADERS,
            json=valid_payload(processing_policy="resume"),
        )
        response = client.get(
            f"/documents/{created.json()['document_id']}/result",
            headers=JOB_HEADERS,
        )

    assert response.status_code == 404
