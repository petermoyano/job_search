from app.schemas import ExtractedJobFacts
from app.services.scoring import score_job


class Profile:
    technical_skills: list[str] = [
        "Python",
        "TypeScript",
        "PostgreSQL",
        "LangChain",
        "RAG",
    ]
    ai_skills: list[str] = ["Agents", "Tool calling", "Embeddings"]
    scoring_weights: dict[str, float] = {}
    deal_breakers: list[str] = ["staffing", "hidden_client", "no_salary_range"]


def test_staffing_language_triggers_configured_deal_breaker() -> None:
    text = """
    Our client has a confidential client looking for a Python engineer.
    This is a staff augmentation role with a client technical interview.
    """
    result = score_job(text, ExtractedJobFacts(company_name=None), Profile())

    assert result.blocked is True
    assert "staffing" in result.triggered_deal_breakers
    assert "hidden_client" in result.triggered_deal_breakers
    assert result.recommendation == "Blocked by deal-breaker"


def test_direct_product_ai_role_scores_well() -> None:
    text = """
    Company: Acme AI
    Role: AI Product Engineer
    We are hiring for our product engineering team building our own SaaS platform.
    The role uses Python, PostgreSQL, LangChain, RAG, embeddings, agents, and tool calling.
    You will meet the hiring manager and product team. Salary range: USD 150,000 - 180,000.
    """
    facts = ExtractedJobFacts(
        company_name="Acme AI", salary_range="USD 150,000 - 180,000"
    )
    result = score_job(text, facts, Profile())

    assert result.blocked is False
    assert result.overall_score >= 70
    assert any(
        line.category == "technical_fit" and line.score >= 65
        for line in result.score_lines
    )
