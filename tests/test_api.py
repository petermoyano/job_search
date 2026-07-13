import os

os.environ["DATABASE_URL"] = "sqlite:///./test_job_radar.db"
os.environ["APP_ENV"] = "test"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def test_create_profile_and_analyze_job() -> None:
    with TestClient(app) as client:
        profile_response = client.post(
            "/profiles",
            json={
                "name": "Test AI Engineer",
                "target_roles": ["AI Engineer"],
                "technical_skills": ["Python", "PostgreSQL", "LangGraph"],
                "ai_skills": ["RAG", "Agents"],
                "deal_breakers": ["staffing", "hidden_client"],
            },
        )
        assert profile_response.status_code == 201
        profile_id = profile_response.json()["id"]

        analysis_response = client.post(
            "/jobs/analyze",
            json={
                "candidate_profile_id": profile_id,
                "title": "AI Product Engineer",
                "company_name": "Acme AI",
                "raw_text": """
                We are hiring an AI Product Engineer for our product engineering team.
                You will build our own SaaS platform with Python, PostgreSQL, LangGraph, RAG, and agents.
                Salary range: USD 150,000 - 180,000. Hiring manager call, product technical discussion, final chat.
                """,
            },
        )

        assert analysis_response.status_code == 201
        payload = analysis_response.json()
        assert payload["job_lead"]["status"] == "analyzed"
        assert payload["analysis"]["overall_score"] > 60
        assert len(payload["analysis"]["score_breakdowns"]) == 5



def test_list_radar_profiles() -> None:
    with TestClient(app) as client:
        response = client.get("/radar/profiles")

    assert response.status_code == 200
    profile_ids = {profile["id"] for profile in response.json()}
    assert "peter-latam-remote-ai-fullstack-product" in profile_ids
    assert "romina-remote-spanish-hr" in profile_ids
    assert "romina-mendoza-hr-onsite-hybrid" in profile_ids


def test_run_radar_with_sample_source() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/radar/runs",
            json={
                "profile_id": "romina-mendoza-hr-onsite-hybrid",
                "source": "sample",
                "limit": 2,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile_id"] == "romina-mendoza-hr-onsite-hybrid"
    assert payload["total_raw"] == 2
    assert payload["total_unique"] == 2
    assert len(payload["items"]) == 2
    assert "candidate" in payload["items"][0]
    assert "classification" in payload["items"][0]


def test_run_radar_unknown_profile_returns_404() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/radar/runs",
            json={"profile_id": "missing-profile", "source": "sample", "limit": 2},
        )

    assert response.status_code == 404


def test_cors_allows_local_next_frontend() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/radar/runs",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
