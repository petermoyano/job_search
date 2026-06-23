from app.graph.workflow import run_job_analysis_workflow


class Profile:
    technical_skills = ["Python", "PostgreSQL", "LangGraph"]
    ai_skills = ["RAG", "Agents"]
    scoring_weights = {}
    deal_breakers = []


def test_job_analysis_workflow_returns_auditable_state() -> None:
    state = run_job_analysis_workflow(
        raw_job_text="""
        Company: ProductCo
        Role: Backend AI Engineer
        Our product engineering team builds a customer-facing product with Python, PostgreSQL, RAG, and agents.
        Salary range: $150k - $180k. Hiring manager call and technical discussion with the product team.
        """,
        candidate_profile=Profile(),
    )

    assert state["facts"].company_name == "ProductCo"
    assert state["scoring_result"].overall_score > 60
    assert state["recommendation"]
    assert [entry["node"] for entry in state["audit_trail"]] == [
        "NormalizeJobText",
        "ExtractStructuredJobFacts",
        "ResolveCompanyType",
        "DetectIntermediarySignals",
        "ScoreAgainstCandidateProfile",
        "GenerateRecommendation",
        "HumanReview",
    ]
