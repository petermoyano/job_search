from __future__ import annotations

import re

from app.radar.models import (
    NormalizedJobCandidate,
    RadarClassification,
    RadarVerdict,
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

PRODUCT_HINTS = [
    "product engineering",
    "product team",
    "our product",
    "our platform",
    "saas",
    "customer-facing",
    "roadmap",
    "users",
]

REMOTE_FRIENDLY_HINTS = [
    "remote - us",
    "remote us",
    "remote, us",
    "remote united states",
    "remote within the united states",
    "united states remote",
    "us remote",
    "americas",
    "north america",
    "latam",
    "latin america",
    "argentina",
    "global remote",
    "remote worldwide",
    "work from anywhere",
    "anywhere in the world",
    "us time zones",
]

STAFFING_HINTS = [
    "staff augmentation",
    "staffing",
    "recruitment agency",
    "third-party recruiter",
    "our client",
    "end client",
    "client is looking",
    "confidential client",
    "implementation partner",
    "consulting engagement",
]

LOCATION_BLOCKERS = [
    "onsite",
    "on-site",
    "hybrid",
    "must be located in",
    "relocation required",
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

    if _contains_any(text, REMOTE_FRIENDLY_HINTS):
        score += 20
        positive.append("mentions LATAM, Americas, global, or US-compatible remote work")
    elif "remote" in text:
        score += 10
        positive.append("mentions remote work")
    else:
        score -= 20
        negative.append("does not clearly mention remote work")

    role_hits = [
        role for role in profile.target_roles if _contains_phrase(text, role.lower())
    ]
    if role_hits:
        score += min(18, 6 * len(role_hits))
        positive.append(f"matches target role terms: {', '.join(role_hits[:3])}")

    if _contains_any(text, PRODUCT_HINTS):
        score += 15
        positive.append("contains product-company or product-engineering signals")

    preferred_hits = [
        term for term in profile.preferred_terms if _contains_phrase(text, term.lower())
    ]
    if preferred_hits:
        score += min(12, 3 * len(preferred_hits))
        positive.append(f"matches preferred terms: {', '.join(preferred_hits[:4])}")

    reject_hits = [
        term
        for term in profile.reject_terms
        if _contains_phrase(text, term.lower()) or _contains_phrase(url, term.lower())
    ]
    if reject_hits:
        score -= min(45, 15 * len(reject_hits))
        negative.append(f"matches reject terms: {', '.join(reject_hits[:4])}")

    if _contains_any(text, STAFFING_HINTS):
        score -= 35
        negative.append("contains staffing, agency, or client-intermediary signals")

    if _contains_any(text, LOCATION_BLOCKERS) and not _contains_any(text, REMOTE_FRIENDLY_HINTS):
        score -= 25
        negative.append("may be onsite, hybrid, or location-restricted")

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
    if score >= 70 and not any("staffing" in item for item in negative):
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


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(_contains_phrase(text, term) for term in terms)


def _contains_phrase(text: str, phrase: str) -> bool:
    pattern = re.escape(phrase.lower()).replace(r"\ ", r"[\s\-]+")
    return bool(re.search(rf"(?<!\w){pattern}(?!\w)", text.lower()))

