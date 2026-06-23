from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.schemas import ExtractedJobFacts
from app.services.text import evidence_for, normalize_text


DEFAULT_WEIGHTS = {
    "directness": 0.25,
    "product_ownership": 0.20,
    "technical_fit": 0.25,
    "ai_depth": 0.20,
    "process_safety": 0.10,
}

SUPPORTED_DEAL_BREAKERS = [
    "staffing",
    "staff_augmentation",
    "outsourcing",
    "hidden_client",
    "third_party_vendor",
    "more_than_4_interview_stages",
    "no_company_name_disclosed",
    "no_salary_range",
    "contractor_only",
    "role_not_involving_hands_on_coding",
    "role_not_involving_ai_engineering",
]


@dataclass(frozen=True)
class SignalRule:
    label: str
    terms: tuple[str, ...]
    category: str
    polarity: str
    points: int


@dataclass
class SignalHit:
    category: str
    label: str
    polarity: str
    confidence: float = 1.0
    evidence: str | None = None


@dataclass
class ScoreLine:
    category: str
    score: int
    weight: float
    rationale: str
    positive_signals: list[str] = field(default_factory=list)
    negative_signals: list[str] = field(default_factory=list)


@dataclass
class ScoringResult:
    overall_score: float
    blocked: bool
    recommendation: str
    recommendation_reason: str
    score_lines: list[ScoreLine]
    signals: list[SignalHit]
    triggered_deal_breakers: list[str]


DIRECTNESS_RULES = [
    SignalRule(
        "company-owned careers page",
        ("careers page", "greenhouse.io", "lever.co", "ashbyhq.com"),
        "directness",
        "positive",
        12,
    ),
    SignalRule(
        "clear company identity",
        ("we are hiring", "our product", "our platform", "our engineering team"),
        "directness",
        "positive",
        10,
    ),
    SignalRule(
        "internal product team",
        (
            "internal product team",
            "product engineering team",
            "report to cto",
            "head of engineering",
        ),
        "directness",
        "positive",
        12,
    ),
    SignalRule(
        "full-time employee",
        ("full-time employee", "permanent employee", "direct hire"),
        "directness",
        "positive",
        10,
    ),
    SignalRule(
        "client reference",
        ("end client", "our client", "client is looking", "client interview"),
        "directness",
        "negative",
        -18,
    ),
    SignalRule(
        "confidential client",
        ("confidential client", "client name confidential", "undisclosed client"),
        "directness",
        "negative",
        -25,
    ),
    SignalRule(
        "staff augmentation",
        (
            "staff augmentation",
            "staff aug",
            "allocated to projects",
            "multiple clients",
        ),
        "directness",
        "negative",
        -25,
    ),
    SignalRule(
        "vendor/intermediary",
        ("vendor", "third-party recruiter", "implementation partner", "nearshore"),
        "directness",
        "negative",
        -18,
    ),
    SignalRule(
        "outsourcing",
        ("outsourcing", "outsourced", "delivery center"),
        "directness",
        "negative",
        -18,
    ),
]

PRODUCT_RULES = [
    SignalRule(
        "own platform",
        ("own platform", "our platform", "proprietary platform"),
        "product_ownership",
        "positive",
        16,
    ),
    SignalRule(
        "SaaS product",
        ("saas", "subscription product", "customer-facing product"),
        "product_ownership",
        "positive",
        14,
    ),
    SignalRule(
        "product roadmap",
        ("product roadmap", "product team", "product engineering"),
        "product_ownership",
        "positive",
        14,
    ),
    SignalRule(
        "internal AI product",
        ("internal ai product", "ai product features", "llm-powered product"),
        "product_ownership",
        "positive",
        12,
    ),
    SignalRule(
        "client projects",
        ("client projects", "client engagements", "rotating assignments"),
        "product_ownership",
        "negative",
        -20,
    ),
    SignalRule(
        "services delivery",
        ("delivery team", "services-only", "consulting engagement"),
        "product_ownership",
        "negative",
        -16,
    ),
]

AI_DEPTH_RULES = [
    SignalRule(
        "RAG/retrieval",
        ("rag", "retrieval augmented generation", "retrieval", "embeddings"),
        "ai_depth",
        "positive",
        14,
    ),
    SignalRule(
        "agentic systems",
        ("agents", "agentic", "tool calling", "function calling"),
        "ai_depth",
        "positive",
        14,
    ),
    SignalRule(
        "LLM evaluation",
        ("evals", "llm evaluation", "model evaluation"),
        "ai_depth",
        "positive",
        12,
    ),
    SignalRule(
        "LLMOps",
        ("llmops", "model routing", "observability", "inference optimization"),
        "ai_depth",
        "positive",
        12,
    ),
    SignalRule(
        "fine-tuning",
        ("fine-tuning", "finetuning", "model training"),
        "ai_depth",
        "positive",
        10,
    ),
    SignalRule(
        "prompt-only role",
        ("prompt engineering only", "write prompts", "prompt specialist"),
        "ai_depth",
        "negative",
        -20,
    ),
    SignalRule(
        "basic chatbot only",
        ("basic chatbot", "simple chatbot", "chatbot only"),
        "ai_depth",
        "negative",
        -18,
    ),
    SignalRule(
        "no-code automation",
        ("zapier", "make.com", "no-code ai", "automation only"),
        "ai_depth",
        "negative",
        -16,
    ),
    SignalRule(
        "vague AI transformation",
        ("ai transformation", "leverage ai", "ai initiatives"),
        "ai_depth",
        "negative",
        -8,
    ),
]

PROCESS_RULES = [
    SignalRule(
        "direct hiring manager",
        ("hiring manager call", "meet the hiring manager", "engineering manager call"),
        "process_safety",
        "positive",
        12,
    ),
    SignalRule(
        "clear salary",
        ("salary range", "compensation range", "base salary"),
        "process_safety",
        "positive",
        10,
    ),
    SignalRule(
        "clear scope",
        ("clear scope", "role scope", "reporting line"),
        "process_safety",
        "positive",
        8,
    ),
    SignalRule(
        "recruiter screen",
        ("recruiter screen", "recruiter interview"),
        "process_safety",
        "negative",
        -8,
    ),
    SignalRule(
        "vendor interview",
        ("vendor technical interview", "vendor interview"),
        "process_safety",
        "negative",
        -16,
    ),
    SignalRule(
        "client interview",
        ("client technical interview", "client final interview", "client interview"),
        "process_safety",
        "negative",
        -16,
    ),
    SignalRule(
        "long take-home",
        ("take-home project", "take home assignment", "long assignment"),
        "process_safety",
        "negative",
        -14,
    ),
    SignalRule(
        "details disclosed on call",
        ("details only disclosed", "more details on a call", "discuss details in call"),
        "process_safety",
        "negative",
        -12,
    ),
]

ALL_RULES = DIRECTNESS_RULES + PRODUCT_RULES + AI_DEPTH_RULES + PROCESS_RULES


def score_job(
    raw_text: str,
    facts: ExtractedJobFacts,
    candidate_profile: Any | None,
) -> ScoringResult:
    normalized = normalize_text(raw_text)
    hits = detect_signals(normalized)
    weights = _weights(candidate_profile)
    score_lines = [
        _keyword_score("directness", hits, weights["directness"]),
        _keyword_score("product_ownership", hits, weights["product_ownership"]),
        _technical_fit_score(
            normalized, facts, candidate_profile, weights["technical_fit"]
        ),
        _keyword_score("ai_depth", hits, weights["ai_depth"]),
        _process_safety_score(normalized, facts, hits, weights["process_safety"]),
    ]
    overall = round(sum(line.score * line.weight for line in score_lines), 2)
    triggered = _triggered_deal_breakers(candidate_profile, facts, score_lines, hits)
    blocked = bool(triggered)
    recommendation, reason = _recommend(overall, score_lines, triggered, hits)
    return ScoringResult(
        overall_score=overall,
        blocked=blocked,
        recommendation=recommendation,
        recommendation_reason=reason,
        score_lines=score_lines,
        signals=hits,
        triggered_deal_breakers=triggered,
    )


def detect_signals(text: str) -> list[SignalHit]:
    hits: list[SignalHit] = []
    lower = text.lower()
    for rule in ALL_RULES:
        term = next(
            (candidate for candidate in rule.terms if candidate.lower() in lower), None
        )
        if term:
            hits.append(
                SignalHit(
                    category=rule.category,
                    label=rule.label,
                    polarity=rule.polarity,
                    confidence=0.95,
                    evidence=evidence_for(text, term),
                )
            )
    return hits


def _keyword_score(category: str, hits: list[SignalHit], weight: float) -> ScoreLine:
    score = 50
    positive: list[str] = []
    negative: list[str] = []
    rule_points = {
        rule.label: rule.points for rule in ALL_RULES if rule.category == category
    }
    for hit in hits:
        if hit.category != category:
            continue
        score += rule_points.get(hit.label, 0)
        if hit.polarity == "positive":
            positive.append(hit.label)
        elif hit.polarity == "negative":
            negative.append(hit.label)
    score = _clamp(score)
    rationale = _rationale(category, score, positive, negative)
    return ScoreLine(category, score, weight, rationale, positive, negative)


def _technical_fit_score(
    text: str,
    facts: ExtractedJobFacts,
    candidate_profile: Any | None,
    weight: float,
) -> ScoreLine:
    target_skills = _profile_list(
        candidate_profile, "technical_skills"
    ) + _profile_list(candidate_profile, "ai_skills")
    if not target_skills:
        target_skills = [
            "Python",
            "TypeScript",
            "React",
            "PostgreSQL",
            "LangChain",
            "LangGraph",
            "RAG",
            "Agents",
        ]
    matched = sorted(
        {skill for skill in target_skills if skill.lower() in text.lower()}
    )
    extracted = set(facts.technologies)
    positive = sorted(set(matched) | extracted.intersection(set(target_skills)))
    score = 35 + round((len(matched) / max(len(set(target_skills)), 1)) * 65)
    if not matched and extracted:
        score = 45
    negative = ["few profile skill matches"] if score < 50 else []
    return ScoreLine(
        "technical_fit",
        _clamp(score),
        weight,
        f"Matched {len(matched)} configured candidate skills against the job text.",
        positive,
        negative,
    )


def _process_safety_score(
    text: str, facts: ExtractedJobFacts, hits: list[SignalHit], weight: float
) -> ScoreLine:
    line = _keyword_score("process_safety", hits, weight)
    score = line.score
    positive = list(line.positive_signals)
    negative = list(line.negative_signals)
    if facts.salary_range:
        score += 8
        positive.append("salary range present")
    else:
        score -= 10
        negative.append("no salary range")
    stage_count = max(len(facts.interview_process), _count_interview_stages(text))
    if 1 <= stage_count <= 3:
        score += 8
        positive.append("reasonable interview stage count")
    elif stage_count > 4:
        score -= 18
        negative.append("more than four interview stages")
    score = _clamp(score)
    return ScoreLine(
        "process_safety",
        score,
        weight,
        f"Process score is based on salary transparency, interview signals, and {stage_count} detected stages.",
        positive,
        negative,
    )


def _triggered_deal_breakers(
    candidate_profile: Any | None,
    facts: ExtractedJobFacts,
    score_lines: list[ScoreLine],
    hits: list[SignalHit],
) -> list[str]:
    requested = {
        value.lower().replace(" ", "_").replace("-", "_")
        for value in _profile_list(candidate_profile, "deal_breakers")
    }
    if not requested:
        return []

    hit_labels = {hit.label for hit in hits}
    score_by_category = {line.category: line.score for line in score_lines}
    triggers = {
        "staffing": {"staff augmentation", "vendor/intermediary"},
        "staff_augmentation": {"staff augmentation"},
        "outsourcing": {"outsourcing"},
        "hidden_client": {"confidential client"},
        "third_party_vendor": {"vendor/intermediary"},
    }
    triggered: list[str] = []
    for breaker, labels in triggers.items():
        if breaker in requested and hit_labels.intersection(labels):
            triggered.append(breaker)
    if "no_salary_range" in requested and not facts.salary_range:
        triggered.append("no_salary_range")
    if "no_company_name_disclosed" in requested and not facts.company_name:
        triggered.append("no_company_name_disclosed")
    if "contractor_only" in requested and (facts.employment_type or "").lower() in {
        "contract",
        "contractor",
        "freelance",
    }:
        triggered.append("contractor_only")
    if "more_than_4_interview_stages" in requested and any(
        "more than four interview stages" in line.negative_signals
        for line in score_lines
    ):
        triggered.append("more_than_4_interview_stages")
    if (
        "role_not_involving_ai_engineering" in requested
        and score_by_category.get("ai_depth", 0) < 45
    ):
        triggered.append("role_not_involving_ai_engineering")
    if "role_not_involving_hands_on_coding" in requested:
        text_fields = " ".join([*facts.responsibilities, *facts.requirements]).lower()
        has_coding_signal = bool(facts.technologies) or any(
            term in text_fields
            for term in {
                "build",
                "develop",
                "implement",
                "code",
                "software",
                "engineering",
            }
        )
        if not has_coding_signal:
            triggered.append("role_not_involving_hands_on_coding")
    return sorted(set(triggered))


def _recommend(
    overall: float,
    score_lines: list[ScoreLine],
    triggered: list[str],
    hits: list[SignalHit],
) -> tuple[str, str]:
    score_by_category = {line.category: line.score for line in score_lines}
    negative_labels = {hit.label for hit in hits if hit.polarity == "negative"}
    if triggered:
        return (
            "Blocked by deal-breaker",
            f"Triggered configured deal-breakers: {', '.join(triggered)}.",
        )
    if {
        "staff augmentation",
        "confidential client",
        "vendor/intermediary",
    } & negative_labels:
        return (
            "Likely staffing: discard",
            "Intermediary or hidden-client language was detected.",
        )
    if overall >= 80 and score_by_category["directness"] >= 60:
        return (
            "Strong fit: apply directly",
            "The opportunity is strong across directness, product ownership, technical fit, and AI depth.",
        )
    if overall >= 70:
        return (
            "Strong fit: investigate company first",
            "The score is strong, but directness or process details should be confirmed.",
        )
    if (
        score_by_category["technical_fit"] >= 65
        and score_by_category["directness"] < 55
    ):
        return (
            "Good technical fit but unclear directness",
            "The role matches the profile, but direct hiring signals are not strong enough yet.",
        )
    if score_by_category["process_safety"] < 45:
        return (
            "High process risk: proceed only if compensation is strong",
            "The process appears inefficient or lacks transparency.",
        )
    if overall >= 50:
        return (
            "Missing data: request more information",
            "The opportunity is not clearly bad, but key evidence is missing.",
        )
    return (
        "Product company but weak technical fit",
        "The score is low enough that this should not be prioritized without new information.",
    )


def _weights(candidate_profile: Any | None) -> dict[str, float]:
    configured = getattr(candidate_profile, "scoring_weights", None) or {}
    weights = DEFAULT_WEIGHTS | {
        key: float(value) for key, value in configured.items() if key in DEFAULT_WEIGHTS
    }
    total = sum(weights.values()) or 1.0
    return {key: value / total for key, value in weights.items()}


def _profile_list(candidate_profile: Any | None, field_name: str) -> list[str]:
    if candidate_profile is None:
        return []
    value = getattr(candidate_profile, field_name, None) or []
    return list(value)


def _count_interview_stages(text: str) -> int:
    markers = [
        "screen",
        "interview",
        "technical",
        "final",
        "take-home",
        "hiring manager",
    ]
    return sum(1 for marker in markers if marker in text.lower())


def _rationale(
    category: str, score: int, positive: list[str], negative: list[str]
) -> str:
    parts = [f"{category.replace('_', ' ').title()} scored {score}/100."]
    if positive:
        parts.append(f"Positive signals: {', '.join(positive)}.")
    if negative:
        parts.append(f"Negative signals: {', '.join(negative)}.")
    if not positive and not negative:
        parts.append("No strong explicit signals were detected.")
    return " ".join(parts)


def _clamp(score: int) -> int:
    return max(0, min(100, score))
