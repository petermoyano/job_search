from __future__ import annotations

import re

from app.radar.models import NormalizedJobCandidate


def dedupe_candidates(
    candidates: list[NormalizedJobCandidate],
) -> list[NormalizedJobCandidate]:
    seen: set[str] = set()
    unique: list[NormalizedJobCandidate] = []
    for candidate in candidates:
        key = candidate_identity_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def candidate_identity_key(candidate: NormalizedJobCandidate) -> str:
    title = _slug(candidate.title or "")
    company = _slug(candidate.company_name or "")
    location = _slug(candidate.location_text or "")
    if title and company:
        return f"job:{company}:{title}:{location}"
    if candidate.canonical_url:
        return f"url:{candidate.canonical_url}"
    return f"job:{company}:{title}:{location}"


def candidate_url_key(candidate: NormalizedJobCandidate) -> str:
    return f"url:{candidate.canonical_url}"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
