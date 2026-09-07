from __future__ import annotations

import re
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.schemas import StructuredCandidateProfile
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
