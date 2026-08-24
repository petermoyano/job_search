from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import delete

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.documents.auth import AuthContext, credential_store
from app.documents.models import Document, DocumentStatus
from app.documents.repository import DocumentRepository
from app.documents.schemas import UploadUrlRequest
from app.documents.service import DocumentService, build_s3_key
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

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        session.execute(delete(Document))
        session.commit()

    storage = FakeStorage()
    app.dependency_overrides[get_document_storage] = lambda: storage
    yield storage

    app.dependency_overrides.pop(get_document_storage, None)
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
