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
