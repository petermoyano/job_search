from __future__ import annotations

import re

from app.radar.models import (
    NormalizedJobCandidate,
    RadarClassification,
    RadarVerdict,
    ScoringGroup,
    SearchProfile,
)


DIRECT_SOURCE_HINTS = [
    "boards.greenhouse.io",
    "jobs.lever.co",
    "ashbyhq.com",
    "smartrecruiters.com",
    "myworkdayjobs.com",
    "careers.",
    "/careers",
    "/jobs",
]


def classify_candidate(
    candidate: NormalizedJobCandidate, profile: SearchProfile
) -> RadarClassification:
    text = candidate.searchable_text.lower()
    url = candidate.canonical_url.lower()
    score = 35
    positive: list[str] = []
    negative: list[str] = []

    if _contains_any(url, DIRECT_SOURCE_HINTS):
        score += 15
        positive.append("appears on a company or ATS-hosted careers page")

    missing_required = [
        term for term in profile.required_terms if not _contains_phrase(text, term.lower())
    ]
    if profile.required_terms and len(missing_required) == len(profile.required_terms):
        score -= 20
        negative.append(
            "does not match required profile terms: "
            f"{', '.join(profile.required_terms[:4])}"
        )

    role_hits = [
        role for role in profile.target_roles if _contains_phrase(text, role.lower())
    ]
    if role_hits:
        score += min(18, 6 * len(role_hits))
        positive.append(f"matches target role terms: {', '.join(role_hits[:3])}")

    preferred_hits = [
        term for term in profile.preferred_terms if _contains_phrase(text, term.lower())
    ]
    if preferred_hits:
        score += min(12, 3 * len(preferred_hits))
        positive.append(f"matches preferred terms: {', '.join(preferred_hits[:4])}")

    for group in profile.positive_scoring_groups:
        hits = _group_hits(text, url, group)
        if hits:
            score += max(0, group.points)
            positive.append(f"{group.label}: {', '.join(hits[:4])}")

    reject_hits = [
        term
        for term in profile.reject_terms
        if _contains_phrase(text, term.lower()) or _contains_phrase(url, term.lower())
    ]
    if reject_hits:
        score -= min(60, 15 * len(reject_hits))
        negative.append(f"matches reject terms: {', '.join(reject_hits[:4])}")

    for group in profile.negative_scoring_groups:
        hits = _group_hits(text, url, group)
        if hits:
            score -= abs(group.points)
            negative.append(f"{group.label}: {', '.join(hits[:4])}")

    bounded_score = max(0, min(100, score))
    verdict = _verdict_for_score(bounded_score, negative)
    reasons = _reasons_for(verdict, positive, negative)
    return RadarClassification(
        verdict=verdict,
        score=bounded_score,
        reasons=reasons,
        positive_signals=positive,
        negative_signals=negative,
        needs_review=verdict != RadarVerdict.reject,
    )


def _verdict_for_score(score: int, negative: list[str]) -> RadarVerdict:
    severe_negative = any(
        label in item.lower()
        for item in negative
        for label in [
            "required english",
            "not local to mendoza",
            "staffing",
            "intermediary",
            "us-only",
        ]
    )
    if score >= 70 and not severe_negative:
        return RadarVerdict.promising
    if score >= 45:
        return RadarVerdict.maybe
    return RadarVerdict.reject


def _reasons_for(
    verdict: RadarVerdict, positive: list[str], negative: list[str]
) -> list[str]:
    if verdict == RadarVerdict.promising:
        return positive[:3] or ["strong first-pass fit"]
    if verdict == RadarVerdict.maybe:
        return (positive[:2] + negative[:2]) or ["needs manual review"]
    return negative[:3] or ["weak match for this radar profile"]


def _group_hits(text: str, url: str, group: ScoringGroup) -> list[str]:
    return [
        term
        for term in group.terms
        if _contains_phrase(text, term.lower()) or _contains_phrase(url, term.lower())
    ]


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(_contains_phrase(text, term) for term in terms)


def _contains_phrase(text: str, phrase: str) -> bool:
    pattern = re.escape(phrase.lower()).replace(r"\ ", r"[\s\-]+")
    return bool(re.search(rf"(?<!\w){pattern}(?!\w)", text.lower()))
