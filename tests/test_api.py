import os
from types import SimpleNamespace
from uuid import uuid4

os.environ["DATABASE_URL"] = "sqlite:///./test_job_radar_v2.db"
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
    assert payload["run_id"]
    assert payload["items"][0]["opportunity_id"]
    assert "candidate" in payload["items"][0]
    assert "classification" in payload["items"][0]


def test_run_radar_unknown_profile_returns_404() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/radar/runs",
            json={"profile_id": "missing-profile", "source": "sample", "limit": 2},
        )

    assert response.status_code == 404


def test_cors_allows_production_frontend() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/radar/runs",
            headers={
                "Origin": "https://job-search-fe.vercel.app",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "https://job-search-fe.vercel.app"
    )


def test_remote_radar_persists_feedback_and_suppresses_repeats(monkeypatch) -> None:
    run_token = uuid4().hex

    monkeypatch.setattr(
        "app.radar.connectors.tavily.get_settings",
        lambda: SimpleNamespace(tavily_api_key="test-api-key"),
    )

    def fake_post_json(_url, payload):
        query = payload["query"]
        if "HR Business Partner" in query:
            tier = 1
            title = "HR Business Partner Senior"
        elif "IT Recruiter" in query:
            tier = 2
            title = "IT Recruiter Senior"
        else:
            tier = 3
            title = "Coordinador de RRHH Senior"
        return {
            "results": [
                {
                    "title": title,
                    "url": f"https://example.com/jobs/{run_token}-{tier}",
                    "raw_content": (
                        "Buscamos profesional senior de recursos humanos para trabajo "
                        "100% remoto desde Argentina con equipos de América Latina. "
                        "Se requieren cinco años de experiencia en selección, talento, "
                        "relaciones laborales y acompañamiento a líderes. Toda la "
                        "publicación está en español. Postularme ahora."
                    ),
                    "published_date": "2026-07-29T12:00:00Z",
                }
            ]
        }

    def fake_hydrate(items):
        return [
            item.model_copy(
                update={
                    "metadata": {
                        **item.metadata,
                        "page_fetched": True,
                        "page_http_status": 200,
                        "application_text": "Postularme ahora",
                    }
                }
            )
            for item in items
        ]

    monkeypatch.setattr("app.radar.connectors.tavily._post_json", fake_post_json)
    monkeypatch.setattr("app.radar.discovery.hydrate_discoveries", fake_hydrate)

    request = {
        "profile_id": "romina-remote-spanish-hr",
        "source": "tavily",
        "limit": 25,
    }
    with TestClient(app) as client:
        first = client.post("/radar/runs", json=request)
        assert first.status_code == 200
        first_payload = first.json()
        assert first_payload["total_new"] == 3
        assert len(first_payload["items"]) == 3
        opportunity_id = first_payload["items"][0]["opportunity_id"]

        invalid_feedback = client.put(
            f"/radar/opportunities/{opportunity_id}/feedback",
            json={
                "profile_id": "romina-remote-spanish-hr",
                "action": "not_relevant",
            },
        )
        assert invalid_feedback.status_code == 422

        feedback = client.put(
            f"/radar/opportunities/{opportunity_id}/feedback",
            json={
                "profile_id": "romina-remote-spanish-hr",
                "action": "not_relevant",
                "reason_codes": ["closed"],
                "notes": "La plataforma confirmó que ya cerró.",
            },
        )
        assert feedback.status_code == 200
        assert feedback.json()["reason_codes"] == ["closed"]

        history = client.get(
            "/radar/opportunities",
            params={"profile_id": "romina-remote-spanish-hr"},
        )
        assert history.status_code == 200
        matching = [item for item in history.json() if item["id"] == opportunity_id]
        assert matching[0]["feedback"]["action"] == "not_relevant"

        second = client.post("/radar/runs", json=request)
        assert second.status_code == 200
        second_payload = second.json()
        assert second_payload["total_new"] == 0
        assert second_payload["items"] == []
        assert second_payload["excluded_items"]
