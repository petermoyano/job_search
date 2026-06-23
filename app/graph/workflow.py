from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.schemas import ExtractedJobFacts
from app.services.extraction import extract_job_facts
from app.services.scoring import ScoringResult, detect_signals, score_job
from app.services.text import normalize_text


class JobRadarState(TypedDict, total=False):
    raw_job_text: str
    normalized_job_text: str
    title: str | None
    company_name: str | None
    source_metadata: dict[str, Any]
    candidate_profile: Any | None
    facts: ExtractedJobFacts
    signals: list[Any]
    scoring_result: ScoringResult
    recommendation: str
    human_decision: dict[str, Any] | None
    audit_trail: list[dict[str, Any]]


def build_job_analysis_graph():
    graph = StateGraph(JobRadarState)
    graph.add_node("normalize_job_text", normalize_job_text_node)
    graph.add_node("extract_structured_job_facts", extract_structured_job_facts_node)
    graph.add_node("resolve_company_type", resolve_company_type_node)
    graph.add_node("detect_intermediary_signals", detect_intermediary_signals_node)
    graph.add_node(
        "score_against_candidate_profile", score_against_candidate_profile_node
    )
    graph.add_node("generate_recommendation", generate_recommendation_node)
    graph.add_node("human_review", human_review_node)

    graph.set_entry_point("normalize_job_text")
    graph.add_edge("normalize_job_text", "extract_structured_job_facts")
    graph.add_edge("extract_structured_job_facts", "resolve_company_type")
    graph.add_edge("resolve_company_type", "detect_intermediary_signals")
    graph.add_edge("detect_intermediary_signals", "score_against_candidate_profile")
    graph.add_edge("score_against_candidate_profile", "generate_recommendation")
    graph.add_edge("generate_recommendation", "human_review")
    graph.add_edge("human_review", END)
    return graph.compile()


def run_job_analysis_workflow(
    raw_job_text: str,
    candidate_profile: Any | None = None,
    title: str | None = None,
    company_name: str | None = None,
    source_metadata: dict[str, Any] | None = None,
) -> JobRadarState:
    return job_analysis_graph.invoke(
        {
            "raw_job_text": raw_job_text,
            "title": title,
            "company_name": company_name,
            "source_metadata": source_metadata or {},
            "candidate_profile": candidate_profile,
            "audit_trail": [],
        }
    )


def normalize_job_text_node(state: JobRadarState) -> JobRadarState:
    normalized = normalize_text(state["raw_job_text"])
    return {
        **state,
        "normalized_job_text": normalized,
        "audit_trail": _audit(
            state, "NormalizeJobText", "Whitespace and line endings normalized."
        ),
    }


def extract_structured_job_facts_node(state: JobRadarState) -> JobRadarState:
    facts = extract_job_facts(
        state["normalized_job_text"],
        title=state.get("title"),
        company_name=state.get("company_name"),
    )
    return {
        **state,
        "facts": facts,
        "audit_trail": _audit(
            state,
            "ExtractStructuredJobFacts",
            "Structured job facts extracted from the job text.",
        ),
    }


def resolve_company_type_node(state: JobRadarState) -> JobRadarState:
    facts = state["facts"]
    if not facts.company_type_guess:
        facts.company_type_guess = "unknown"
    return {
        **state,
        "facts": facts,
        "audit_trail": _audit(
            state,
            "ResolveCompanyType",
            f"Company type guess: {facts.company_type_guess}.",
        ),
    }


def detect_intermediary_signals_node(state: JobRadarState) -> JobRadarState:
    signals = detect_signals(state["normalized_job_text"])
    intermediary_count = len(
        [
            signal
            for signal in signals
            if signal.category == "directness" and signal.polarity == "negative"
        ]
    )
    return {
        **state,
        "signals": signals,
        "audit_trail": _audit(
            state,
            "DetectIntermediarySignals",
            f"Detected {intermediary_count} negative directness/intermediary signals.",
        ),
    }


def score_against_candidate_profile_node(state: JobRadarState) -> JobRadarState:
    result = score_job(
        state["normalized_job_text"], state["facts"], state.get("candidate_profile")
    )
    return {
        **state,
        "scoring_result": result,
        "signals": result.signals,
        "audit_trail": _audit(
            state,
            "ScoreAgainstCandidateProfile",
            f"Overall score: {result.overall_score}.",
        ),
    }


def generate_recommendation_node(state: JobRadarState) -> JobRadarState:
    result = state["scoring_result"]
    return {
        **state,
        "recommendation": result.recommendation,
        "audit_trail": _audit(
            state, "GenerateRecommendation", result.recommendation_reason
        ),
    }


def human_review_node(state: JobRadarState) -> JobRadarState:
    return {
        **state,
        "human_decision": None,
        "audit_trail": _audit(state, "HumanReview", "Ready for a human decision."),
    }


def _audit(state: JobRadarState, node: str, summary: str) -> list[dict[str, Any]]:
    return [*state.get("audit_trail", []), {"node": node, "summary": summary}]


job_analysis_graph = build_job_analysis_graph()
