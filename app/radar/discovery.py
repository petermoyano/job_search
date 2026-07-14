from __future__ import annotations

import logging

from app.radar.classify import classify_candidate
from app.radar.connectors.base import DiscoveryConnector
from app.radar.dedupe import dedupe_candidates
from app.radar.models import ClassifiedDiscovery, DiscoveryRunResult, SearchProfile
from app.radar.normalize import normalize_discovery


LOGGER = logging.getLogger(__name__)


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
        LOGGER.info("Running connector=%s remaining_limit=%s", connector.name, remaining)
        before = len(raw_items)
        raw_items.extend(connector.discover(profile, remaining))
        LOGGER.info(
            "Connector finished: connector=%s raw_added=%s raw_total=%s",
            connector.name,
            len(raw_items) - before,
            len(raw_items),
        )

    LOGGER.info("Normalizing discoveries: raw=%s", len(raw_items))
    normalized = [normalize_discovery(item) for item in raw_items]
    unique = dedupe_candidates(normalized)
    LOGGER.info(
        "Deduplicated discoveries: unique=%s duplicates=%s",
        len(unique),
        len(normalized) - len(unique),
    )
    LOGGER.info("Classifying discoveries: unique=%s", len(unique))
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
    counts = _classification_counts(classified)
    LOGGER.info(
        "Classification summary: promising=%s maybe=%s reject=%s",
        counts["promising"],
        counts["maybe"],
        counts["reject"],
    )
    LOGGER.info("Sorted classified discoveries by verdict and score")
    return DiscoveryRunResult(
        profile_id=profile.id,
        total_raw=len(raw_items),
        total_unique=len(unique),
        items=classified,
    )




def _classification_counts(items: list[ClassifiedDiscovery]) -> dict[str, int]:
    counts = {"promising": 0, "maybe": 0, "reject": 0}
    for item in items:
        counts[item.classification.verdict.value] += 1
    return counts
