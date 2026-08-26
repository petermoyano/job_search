from __future__ import annotations

from uuid import UUID, uuid4
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.documents.auth import credential_store
from app.documents.models import Document, DocumentStatus
from app.documents.repository import DocumentRepository
from app.knowledge.api import get_knowledge_retrieval_service
from app.knowledge.contracts import (
    CRANE_INTELLIGENCE_SOURCE_APP,
    KNOWLEDGE_BASE_PROCESSING_POLICY,
)
from app.knowledge.retrieval import (
    KnowledgeBaseRetrievalClient,
    KnowledgeRetrievalResult,
    KnowledgeRetrievalService,
)
from app.main import app


CRANE_SECRET = "test-crane-secret"
JOB_SECRET = "test-job-search-secret"
CRANE_HEADERS = {"Authorization": f"Bearer {CRANE_SECRET}"}
JOB_HEADERS = {"Authorization": f"Bearer {JOB_SECRET}"}


class FakeKnowledgeRetrievalClient:
    def __init__(self, results: list[KnowledgeRetrievalResult]) -> None:
        self.results = results
        self.calls: list[dict] = []

    def retrieve(
        self,
        *,
        knowledge_base_id: str,
        query: str,
        max_results: int,
        metadata_filter: dict,
    ) -> list[KnowledgeRetrievalResult]:
        self.calls.append(
            {
                "knowledge_base_id": knowledge_base_id,
                "query": query,
                "max_results": max_results,
                "metadata_filter": metadata_filter,
            }
        )
        return self.results


@pytest.fixture(autouse=True)
def knowledge_api_test_environment() -> None:
    settings = get_settings()
    original_keys = settings.document_client_keys_json
    original_knowledge_base_id = settings.knowledge_base_id
    settings.document_client_keys_json = json.dumps(
        {
            "test-job-search-secret": {
                "source_app": "job-search",
                "tenant_ids": ["job-search"],
            },
            "test-crane-secret": {
                "source_app": "crane-intelligence",
                "tenant_ids": ["creactis"],
            },
        }
    )
    settings.knowledge_base_id = "KB123"
    credential_store.clear_cache()

    assert engine.dialect.name == "sqlite"
    Base.metadata.create_all(bind=engine)
    Document.__table__.drop(bind=engine, checkfirst=True)
    Document.__table__.create(bind=engine)
    with SessionLocal() as session:
        session.execute(delete(Document))
        session.commit()

    yield

    app.dependency_overrides.pop(get_knowledge_retrieval_service, None)
    credential_store.clear_cache()
    settings.document_client_keys_json = original_keys
    settings.knowledge_base_id = original_knowledge_base_id


def create_rag_document(*, document_id: UUID, tenant_id: str) -> None:
    with SessionLocal() as session:
        session.add(
            Document(
                id=document_id,
                tenant_id=tenant_id,
                project_id="project-1",
                source_app=CRANE_INTELLIGENCE_SOURCE_APP,
                processing_policy=KNOWLEDGE_BASE_PROCESSING_POLICY,
                context={},
                original_filename="manual.pdf",
                mime_type="application/pdf",
                file_size_bytes=128,
                s3_bucket="test-documents",
                s3_key=f"documents/{tenant_id}/crane-intelligence/{document_id}.pdf",
                status=DocumentStatus.RAG_INDEXED,
            )
        )
        session.commit()


def override_retrieval_client(client: KnowledgeBaseRetrievalClient) -> None:
    def get_test_service():
        with SessionLocal() as session:
            yield KnowledgeRetrievalService(
                repository=DocumentRepository(session),
                settings=get_settings(),
                client=client,
            )

    app.dependency_overrides[get_knowledge_retrieval_service] = get_test_service


def test_retrieve_returns_only_authorized_rag_citations() -> None:
    authorized_document_id = uuid4()
    foreign_document_id = uuid4()
    create_rag_document(document_id=authorized_document_id, tenant_id="creactis")
    create_rag_document(document_id=foreign_document_id, tenant_id="other-tenant")
    client = FakeKnowledgeRetrievalClient(
        [
            KnowledgeRetrievalResult(
                text="Procedimiento para inspeccionar el freno de izado.",
                score=0.91,
                metadata={
                    "document_id": str(authorized_document_id),
                    "document_title": "Manual de freno",
                    "tenant_id": "creactis",
                    "source_app": CRANE_INTELLIGENCE_SOURCE_APP,
                    "s3_uri": "s3://private/never-returned.pdf",
                },
            ),
            KnowledgeRetrievalResult(
                text="Contenido de otro tenant.",
                score=0.99,
                metadata={
                    "document_id": str(foreign_document_id),
                    "document_title": "Otro manual",
                },
            ),
        ]
    )
    override_retrieval_client(client)

    with TestClient(app) as http_client:
        response = http_client.post(
            "/knowledge/retrieve",
            headers=CRANE_HEADERS,
            json={
                "query": "¿Cómo inspecciono el freno?",
                "project_id": "project-1",
                "max_results": 5,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "¿Cómo inspecciono el freno?"
    assert payload["citations"] == [
        {
            "document_id": str(authorized_document_id),
            "title": "Manual de freno",
            "excerpt": "Procedimiento para inspeccionar el freno de izado.",
            "score": 0.91,
            "page_number": None,
        }
    ]
    assert "s3_uri" not in response.text
    assert client.calls == [
        {
            "knowledge_base_id": "KB123",
            "query": "¿Cómo inspecciono el freno?",
            "max_results": 5,
            "metadata_filter": {
                "andAll": [
                    {
                        "equals": {
                            "key": "source_app",
                            "value": CRANE_INTELLIGENCE_SOURCE_APP,
                        }
                    },
                    {"in": {"key": "tenant_id", "value": ["creactis"]}},
                    {"equals": {"key": "project_id", "value": "project-1"}},
                ]
            },
        }
    ]


def test_retrieve_rejects_credential_for_another_source_app() -> None:
    client = FakeKnowledgeRetrievalClient([])
    override_retrieval_client(client)

    with TestClient(app) as http_client:
        response = http_client.post(
            "/knowledge/retrieve",
            headers=JOB_HEADERS,
            json={"query": "inspección de freno"},
        )

    assert response.status_code == 403
    assert client.calls == []


def test_retrieve_requires_a_bearer_credential() -> None:
    with TestClient(app) as http_client:
        response = http_client.post(
            "/knowledge/retrieve",
            json={"query": "inspección de freno"},
        )

    assert response.status_code == 401
