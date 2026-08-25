from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.documents.auth import credential_store
from app.documents.models import (
    Document,
    DocumentStatus,
    ResumeProfileDraft,
    now_utc,
)
from app.main import app
from app.models import RadarProfileConfig


PROFILE_ID = "peter-latam-remote-ai-fullstack-product"
JOB_SECRET = "test-job-search-secret"
JOB_HEADERS = {"Authorization": f"Bearer {JOB_SECRET}"}


def draft_payload() -> dict:
    return {
        "full_name": "Jane Synthetic",
        "headline": "Software Engineer",
        "professional_summary": "Builds reliable software systems.",
        "location": "Buenos Aires",
        "email": "jane@example.test",
        "phone": None,
        "linkedin_url": None,
        "github_url": None,
        "skills": [
            {"name": "Python", "category": "language", "confidence": 0.99},
            {"name": "python", "category": "language", "confidence": 0.90},
            {"name": "TypeScript", "category": "language", "confidence": 0.95},
        ],
        "experience": [
            {
                "company": "Synthetic Labs",
                "title": "Engineer",
                "location": "Remote",
                "start_date": "2022-01",
                "end_date": None,
                "is_current": True,
                "description": "Built test systems.",
                "source_pages": [1],
            },
            {
                "company": "synthetic labs",
                "title": "engineer",
                "location": "Remote",
                "start_date": "2022-01",
                "end_date": None,
                "is_current": True,
                "description": "Duplicate.",
                "source_pages": [1],
            },
        ],
        "education": [
            {
                "institution": "Example University",
                "degree": "BS",
                "field_of_study": "Computing",
                "start_date": "2017",
                "end_date": "2021",
                "source_pages": [2],
            }
        ],
        "languages": [
            {"language": "Spanish", "level": "native", "raw_level": "Nativo"}
        ],
        "certifications": [
            {"name": "Cloud Test", "issuer": "Example", "date": "2024"}
        ],
    }


@pytest.fixture(autouse=True)
def resume_apply_environment() -> None:
    settings = get_settings()
    original = settings.document_client_keys_json
    settings.document_client_keys_json = (
        '{"test-job-search-secret":{"source_app":"job-search",'
        '"tenant_ids":["job-search"]}}'
    )
    credential_store.clear_cache()
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        session.execute(delete(ResumeProfileDraft))
        session.execute(delete(Document))
        session.execute(delete(RadarProfileConfig))
        session.commit()
    yield
    credential_store.clear_cache()
    settings.document_client_keys_json = original


def create_draft(
    *,
    profile_id: str = PROFILE_ID,
    tenant_id: str = "job-search",
    status: DocumentStatus = DocumentStatus.COMPLETED,
) -> tuple[str, str]:
    document_id = uuid4()
    draft_id = uuid4()
    with SessionLocal() as session:
        document = Document(
            id=document_id,
            tenant_id=tenant_id,
            source_app="job-search",
            processing_policy="resume",
            context={"profile_id": profile_id},
            original_filename="synthetic.pdf",
            mime_type="application/pdf",
            file_size_bytes=128,
            s3_bucket="test",
            s3_key=f"documents/{document_id}/original.pdf",
            status=status,
        )
        session.add(document)
        session.flush()
        session.add(
            ResumeProfileDraft(
                id=draft_id,
                document_id=document_id,
                tenant_id=tenant_id,
                source_app="job-search",
                profile_id=profile_id,
                schema_version="1",
                payload=draft_payload(),
                model_id="test-model",
                extracted_at=now_utc(),
            )
        )
        session.commit()
    return str(document_id), str(draft_id)


def apply_draft(
    client: TestClient,
    draft_id: str,
    *,
    profile_id: str = PROFILE_ID,
    sections: list[str],
    expected_revision: int = 0,
):
    return client.post(
        f"/resume-profile-drafts/{draft_id}/apply",
        headers=JOB_HEADERS,
        json={
            "profile_id": profile_id,
            "sections": sections,
            "expected_revision": expected_revision,
        },
    )


def test_apply_is_selective_deduplicated_and_preserves_radar_settings() -> None:
    _document_id, draft_id = create_draft()
    sections = ["professional_summary", "skills", "experience"]
    with TestClient(app) as client:
        before = client.get(f"/radar/profiles/{PROFILE_ID}/config").json()
        response = apply_draft(client, draft_id, sections=sections)
        repeated = apply_draft(
            client,
            draft_id,
            sections=sections,
            expected_revision=1,
        )

    assert response.status_code == 200
    body = response.json()
    professional = body["profile"]["professional_profile"]
    assert body["profile"]["candidate_summary"] == (
        "Builds reliable software systems."
    )
    assert [item["name"] for item in professional["skills"]] == [
        "Python",
        "TypeScript",
    ]
    assert len(professional["experience"]) == 1
    assert professional["education"] == []
    assert professional["languages"] == []
    assert repeated.status_code == 200
    assert repeated.json()["profile"]["professional_profile"] == professional

    protected = [
        "target_roles",
        "role_tiers",
        "location_policy",
        "eligibility_policy",
        "required_terms",
        "preferred_terms",
        "reject_terms",
        "ordered_sources",
        "source_references",
        "preferred_source_domains",
        "excluded_source_domains",
        "queries",
        "max_results_per_query",
        "max_qualified_results",
    ]
    for field in protected:
        assert body["profile"][field] == before["profile"][field]

    with SessionLocal() as session:
        draft = session.scalar(
            select(ResumeProfileDraft).where(
                ResumeProfileDraft.id == UUID(draft_id)
            )
        )
        assert draft is not None
        assert draft.applied_at is not None


def test_draft_from_another_tenant_is_not_found() -> None:
    _document_id, draft_id = create_draft(tenant_id="other-tenant")
    with TestClient(app) as client:
        response = apply_draft(client, draft_id, sections=["skills"])
    assert response.status_code == 404


def test_wrong_profile_and_nonexistent_draft_are_rejected() -> None:
    _document_id, draft_id = create_draft()
    with TestClient(app) as client:
        wrong = apply_draft(
            client,
            draft_id,
            profile_id="romina-remote-spanish-hr",
            sections=["skills"],
        )
        missing = apply_draft(client, str(uuid4()), sections=["skills"])
    assert wrong.status_code == 409
    assert missing.status_code == 404


@pytest.mark.parametrize(
    "document_status",
    [DocumentStatus.REJECTED, DocumentStatus.NEEDS_REVIEW],
)
def test_non_completed_document_cannot_be_applied(
    document_status: DocumentStatus,
) -> None:
    _document_id, draft_id = create_draft(status=document_status)
    with TestClient(app) as client:
        response = apply_draft(client, draft_id, sections=["skills"])
    assert response.status_code == 409


def test_profile_document_list_is_scoped_and_supports_refresh() -> None:
    matching_id, _draft_id = create_draft()
    create_draft(profile_id="romina-remote-spanish-hr")
    with TestClient(app) as client:
        response = client.get(
            f"/profiles/{PROFILE_ID}/resume-documents",
            headers=JOB_HEADERS,
        )
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [matching_id]


def test_stale_profile_revision_is_rejected() -> None:
    _document_id, draft_id = create_draft()
    with TestClient(app) as client:
        first = apply_draft(client, draft_id, sections=["skills"])
        stale = apply_draft(client, draft_id, sections=["skills"])
    assert first.status_code == 200
    assert stale.status_code == 409
