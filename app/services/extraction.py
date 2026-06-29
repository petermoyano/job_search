from __future__ import annotations

import re
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.schemas import ExtractedJobFacts, StructuredCandidateProfile
from app.services.text import normalize_text


TECH_TERMS = [
    "Python",
    "TypeScript",
    "JavaScript",
    "Next.js",
    "React",
    "Node.js",
    "FastAPI",
    "PostgreSQL",
    "SQLAlchemy",
    "LangChain",
    "LangGraph",
    "LlamaIndex",
    "RAG",
    "Agents",
    "Tool calling",
    "Function calling",
    "OpenAI",
    "Anthropic",
    "Vector database",
    "Pinecone",
    "Weaviate",
    "pgvector",
    "Embeddings",
    "Evals",
    "LLMOps",
    "Ollama",
    "Hugging Face",
    "Local inference",
    "Docker",
    "AWS",
]

ROLE_TERMS = [
    "AI Engineer",
    "Full-stack AI Engineer",
    "Applied AI Engineer",
    "LLM Engineer",
    "AI Product Engineer",
    "Backend AI Engineer",
    "RAG Engineer",
    "Agentic AI Engineer",
    "Software Engineer",
    "Full-stack Developer",
    "Backend Engineer",
]


class LLMProfileOutput(BaseModel):
    target_roles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    seniority: str | None = None
    technical_skills: list[str] = Field(default_factory=list)
    ai_skills: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    summary: str | None = None


def extract_candidate_profile(
    raw_text: str, use_llm: bool = False
) -> tuple[StructuredCandidateProfile, str]:
    if use_llm:
        llm_result = _try_extract_profile_with_llm(raw_text)
        if llm_result is not None:
            return llm_result, "llm_structured_output"
    return _extract_candidate_profile_deterministic(raw_text), "deterministic"


def extract_job_facts(
    raw_text: str, title: str | None = None, company_name: str | None = None
) -> ExtractedJobFacts:
    normalized = normalize_text(raw_text)
    return ExtractedJobFacts(
        title=title
        or _extract_labeled_value(normalized, ["role", "title", "position"]),
        company_name=company_name
        or _extract_labeled_value(normalized, ["company", "client"]),
        employment_type=_extract_employment_type(normalized),
        location=_extract_labeled_value(normalized, ["location", "work location"]),
        salary_range=_extract_salary(normalized),
        interview_process=_extract_interview_steps(normalized),
        responsibilities=_extract_section_items(
            normalized, ["responsibilities", "what you will do", "the role"]
        ),
        requirements=_extract_section_items(
            normalized, ["requirements", "qualifications", "what we are looking for"]
        ),
        technologies=_extract_terms(normalized, TECH_TERMS),
        company_type_guess=_guess_company_type(normalized),
    )


def _try_extract_profile_with_llm(raw_text: str) -> StructuredCandidateProfile | None:
    settings = get_settings()
    if not settings.openai_api_key:
        return None

    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        return None

    prompt = (
        "Extract a structured candidate profile from this CV text. "
        "Only include skills and roles that are supported by the text.\n\n"
        f"{raw_text}"
    )
    model = ChatOpenAI(model=settings.llm_model, temperature=0).with_structured_output(
        LLMProfileOutput
    )
    result = model.invoke(prompt)
    if isinstance(result, BaseModel):
        return StructuredCandidateProfile.model_validate(result.model_dump())
    return StructuredCandidateProfile.model_validate(result)


def _extract_candidate_profile_deterministic(
    raw_text: str,
) -> StructuredCandidateProfile:
    normalized = normalize_text(raw_text)
    found_roles = _extract_terms(normalized, ROLE_TERMS)
    found_tech = _extract_terms(normalized, TECH_TERMS)
    ai_skills = [
        skill
        for skill in found_tech
        if skill.lower()
        in {
            "langchain",
            "langgraph",
            "llamaindex",
            "rag",
            "agents",
            "tool calling",
            "function calling",
            "openai",
            "anthropic",
            "vector database",
            "embeddings",
            "evals",
            "llmops",
            "ollama",
            "hugging face",
            "local inference",
        }
    ]
    seniority = (
        "senior"
        if re.search(r"\bsenior\b|\blead\b|\bprincipal\b", normalized, re.I)
        else None
    )
    languages = _extract_terms(
        normalized, ["English", "Spanish", "Portuguese", "French", "German"]
    )
    locations = _extract_terms(
        normalized, ["Remote", "Argentina", "United States", "Europe", "LATAM"]
    )
    summary = normalized[:500]
    return StructuredCandidateProfile(
        target_roles=found_roles,
        preferred_locations=locations,
        seniority=seniority,
        technical_skills=found_tech,
        ai_skills=ai_skills,
        languages=languages,
        summary=summary,
    )


def _extract_terms(text: str, terms: list[str]) -> list[str]:
    found: list[str] = []
    for term in terms:
        pattern = re.escape(term).replace(r"\ ", r"[\s-]+")
        if re.search(rf"(?<!\w){pattern}(?!\w)", text, flags=re.IGNORECASE):
            found.append(term)
    return found


def _extract_labeled_value(text: str, labels: list[str]) -> str | None:
    for label in labels:
        match = re.search(rf"(?im)^\s*{re.escape(label)}\s*:\s*(.+)$", text)
        if match:
            return match.group(1).strip()
    return None


def _extract_salary(text: str) -> str | None:
    salary_patterns = [
        r"(?i)(?:USD|US\$|\$)\s?\d{2,3}(?:,\d{3})?(?:\s?-\s?(?:USD|US\$|\$)?\s?\d{2,3}(?:,\d{3})?)?",
        r"(?i)\d{2,3}k\s?-\s?\d{2,3}k",
        r"(?i)salary(?: range)?\s*:\s*(.+)",
    ]
    for pattern in salary_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0).strip()
    return None


def _extract_employment_type(text: str) -> str | None:
    employment_types = [
        "full-time",
        "part-time",
        "contract",
        "contractor",
        "freelance",
        "employee",
        "permanent",
    ]
    found = _extract_terms(text, employment_types)
    return found[0] if found else None


def _extract_interview_steps(text: str) -> list[str]:
    steps: list[str] = []
    for line in text.splitlines():
        if re.search(
            r"interview|screen|call|take-home|technical|final|stage", line, re.I
        ):
            steps.append(line.strip("-* "))
    return steps[:10]


def _extract_section_items(text: str, section_names: list[str]) -> list[str]:
    lines = text.splitlines()
    items: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        if any(
            re.search(rf"^{re.escape(name)}\b", stripped, re.I)
            for name in section_names
        ):
            in_section = True
            continue
        if in_section and re.search(r"^[A-Z][A-Za-z\s]{2,}:$", stripped):
            break
        if in_section and stripped:
            items.append(stripped.strip("-* "))
        if len(items) >= 8:
            break
    return items


def _guess_company_type(text: str) -> str | None:
    guesses: list[tuple[str, list[str]]] = [
        (
            "staffing_or_vendor",
            [
                "staff augmentation",
                "vendor",
                "end client",
                "confidential client",
                "client interview",
            ],
        ),
        ("consulting", ["consulting", "implementation partner", "client projects"]),
        (
            "product_company",
            [
                "own platform",
                "saas",
                "product team",
                "product roadmap",
                "customer-facing product",
            ],
        ),
    ]
    lower = text.lower()
    for guess, terms in guesses:
        if any(term in lower for term in terms):
            return guess
    return None
