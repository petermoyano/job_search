from __future__ import annotations

from app.radar.classify import classify_candidate
from app.radar.connectors.base import DiscoveryConnector
from app.radar.dedupe import dedupe_candidates
from app.radar.models import ClassifiedDiscovery, DiscoveryRunResult, SearchProfile
from app.radar.normalize import normalize_discovery


def run_discovery(
    profile: SearchProfile,
    connectors: list[DiscoveryConnector],
    limit: int = 50,
) -> DiscoveryRunResult:
    raw_items = []
    for connector in connectors:
        remaining = max(0, limit - len(raw_items))
        if remaining == 0:
            break
        raw_items.extend(connector.discover(profile, remaining))

    normalized = [normalize_discovery(item) for item in raw_items]
    unique = dedupe_candidates(normalized)
    classified = [
        ClassifiedDiscovery(
            candidate=candidate,
            classification=classify_candidate(candidate, profile),
        )
        for candidate in unique
    ]
    classified.sort(
        key=lambda item: (
            item.classification.verdict != "promising",
            -item.classification.score,
            item.candidate.company_name or "",
            item.candidate.title or "",
        )
    )
    return DiscoveryRunResult(
        profile_id=profile.id,
        total_raw=len(raw_items),
        total_unique=len(unique),
        items=classified,
    )

