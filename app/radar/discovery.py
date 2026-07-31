from __future__ import annotations

import logging

from app.radar.classify import classify_candidate
from app.radar.connectors.base import DiscoveryConnector
from app.radar.dedupe import (
    candidate_identity_key,
    candidate_url_key,
    dedupe_candidates,
)
from app.radar.hydrate import hydrate_discoveries
from app.radar.models import (
    ClassifiedDiscovery,
    DiscoveryRunResult,
    NormalizedJobCandidate,
    RawDiscovery,
    SearchProfile,
    SourceRunSummary,
)
from app.radar.normalize import normalize_discovery


LOGGER = logging.getLogger(__name__)


def run_discovery(
    profile: SearchProfile,
    connectors: list[DiscoveryConnector],
    limit: int = 50,
    suppressed_keys: set[str] | None = None,
    hydrate: bool = True,
) -> DiscoveryRunResult:
    suppressed = suppressed_keys or set()
    ordered_connector = next(
        (
            connector
            for connector in connectors
            if profile.ordered_sources and hasattr(connector, "discover_source")
        ),
        None,
    )
    if ordered_connector is not None:
        return _run_ordered_discovery(
            profile=profile,
            connector=ordered_connector,
            limit=limit,
            suppressed_keys=suppressed,
            hydrate=hydrate,
        )
    return _run_connector_discovery(
        profile=profile,
        connectors=connectors,
        limit=limit,
        suppressed_keys=suppressed,
        hydrate=hydrate,
    )


def _run_ordered_discovery(
    *,
    profile: SearchProfile,
    connector: DiscoveryConnector,
    limit: int,
    suppressed_keys: set[str],
    hydrate: bool,
) -> DiscoveryRunResult:
    raw_total = 0
    all_classified: list[ClassifiedDiscovery] = []
    displayed: list[ClassifiedDiscovery] = []
    excluded: list[ClassifiedDiscovery] = []
    summaries: list[SourceRunSummary] = []
    seen_keys: set[str] = set()
    target = min(profile.max_qualified_results, limit)
    ordered_sources = sorted(profile.ordered_sources, key=lambda item: item.order)

    for source_index, source in enumerate(ordered_sources):
        if len(displayed) >= target:
            break
        source_limit = min(source.max_results, limit)
        LOGGER.info(
            "Running ordered source=%s order=%s limit=%s",
            source.id,
            source.order,
            source_limit,
        )
        discover_source = getattr(connector, "discover_source")
        raw_items = discover_source(profile, source, source_limit)
        raw_total += len(raw_items)
        classified = _classify_raw_batch(
            profile=profile,
            raw_items=raw_items,
            suppressed_keys=suppressed_keys,
            seen_keys=seen_keys,
            hydrate=hydrate,
        )
        all_classified.extend(classified)
        source_qualified = [item for item in classified if item.classification.eligible]
        source_new = [item for item in source_qualified if item.is_new]
        displayed_before = len(displayed)
        for item in classified:
            if item.classification.eligible and item.is_new and len(displayed) < target:
                displayed.append(item)
            else:
                excluded.append(item)
        source_presented = len(displayed) - displayed_before
        target_reached = len(displayed) >= target
        threshold_met = len(source_new) >= source.min_qualified_to_stop
        source_is_last = source_index == len(ordered_sources) - 1
        stop_reason = (
            "target_reached"
            if target_reached
            else "source_threshold_met"
            if threshold_met
            else "sources_exhausted"
            if source_is_last
            else None
        )

        summary = SourceRunSummary(
            source_id=source.id,
            source_label=source.label,
            raw_count=len(raw_items),
            unique_count=len(classified),
            qualified_count=len(source_qualified),
            new_qualified_count=len(source_new),
            continued_to_next=stop_reason is None,
            stop_reason=stop_reason,
            excluded_count=len(classified) - source_presented,
        )
        summaries.append(summary)
        LOGGER.info(
            "Ordered source summary: source=%s raw=%s unique=%s qualified=%s "
            "new_qualified=%s",
            source.id,
            summary.raw_count,
            summary.unique_count,
            summary.qualified_count,
            summary.new_qualified_count,
        )
        if stop_reason is not None:
            break

    _sort_classified(displayed)
    _sort_classified(excluded)
    return _build_result(
        profile=profile,
        raw_total=raw_total,
        all_classified=all_classified,
        items=displayed,
        excluded=excluded,
        source_summaries=summaries,
    )


def _run_connector_discovery(
    *,
    profile: SearchProfile,
    connectors: list[DiscoveryConnector],
    limit: int,
    suppressed_keys: set[str],
    hydrate: bool,
) -> DiscoveryRunResult:
    raw_items: list[RawDiscovery] = []
    summaries: list[SourceRunSummary] = []
    for connector in connectors:
        remaining = max(0, limit - len(raw_items))
        if remaining == 0:
            break
        LOGGER.info(
            "Running connector=%s remaining_limit=%s", connector.name, remaining
        )
        discovered = connector.discover(profile, remaining)
        raw_items.extend(discovered)
        summaries.append(
            SourceRunSummary(
                source_id=connector.name,
                source_label=connector.name,
                raw_count=len(discovered),
            )
        )

    classified = _classify_raw_batch(
        profile=profile,
        raw_items=raw_items,
        suppressed_keys=suppressed_keys,
        seen_keys=set(),
        hydrate=hydrate,
    )
    if profile.eligibility_policy is None:
        items = classified
        excluded: list[ClassifiedDiscovery] = []
    else:
        items = [
            item for item in classified if item.classification.eligible and item.is_new
        ][: profile.max_qualified_results]
        displayed_ids = {id(item) for item in items}
        excluded = [item for item in classified if id(item) not in displayed_ids]

    _sort_classified(items)
    _sort_classified(excluded)
    if summaries:
        summaries[0] = summaries[0].model_copy(
            update={
                "unique_count": len(classified),
                "qualified_count": sum(
                    item.classification.eligible for item in classified
                ),
                "new_qualified_count": sum(
                    item.classification.eligible and item.is_new for item in classified
                ),
                "excluded_count": len(excluded),
            }
        )
    return _build_result(
        profile=profile,
        raw_total=len(raw_items),
        all_classified=classified,
        items=items,
        excluded=excluded,
        source_summaries=summaries,
    )


def _classify_raw_batch(
    *,
    profile: SearchProfile,
    raw_items: list[RawDiscovery],
    suppressed_keys: set[str],
    seen_keys: set[str],
    hydrate: bool,
) -> list[ClassifiedDiscovery]:
    prepared = (
        hydrate_discoveries(raw_items)
        if hydrate and profile.eligibility_policy is not None
        else raw_items
    )
    normalized = dedupe_candidates([normalize_discovery(item) for item in prepared])
    unique: list[NormalizedJobCandidate] = []
    for candidate in normalized:
        identity_key = candidate_identity_key(candidate)
        url_key = candidate_url_key(candidate)
        if identity_key in seen_keys or url_key in seen_keys:
            continue
        seen_keys.update({identity_key, url_key})
        unique.append(candidate)

    classified: list[ClassifiedDiscovery] = []
    for candidate in unique:
        identity_key = candidate_identity_key(candidate)
        url_key = candidate_url_key(candidate)
        is_new = not (identity_key in suppressed_keys or url_key in suppressed_keys)
        classified.append(
            ClassifiedDiscovery(
                candidate=candidate,
                classification=classify_candidate(candidate, profile),
                is_new=is_new,
            )
        )
    return classified


def _build_result(
    *,
    profile: SearchProfile,
    raw_total: int,
    all_classified: list[ClassifiedDiscovery],
    items: list[ClassifiedDiscovery],
    excluded: list[ClassifiedDiscovery],
    source_summaries: list[SourceRunSummary],
) -> DiscoveryRunResult:
    counts = _classification_counts(all_classified)
    qualified = sum(item.classification.eligible for item in all_classified)
    new_qualified = sum(
        item.classification.eligible and item.is_new for item in all_classified
    )
    LOGGER.info(
        "Classification summary: promising=%s maybe=%s reject=%s qualified=%s new=%s",
        counts["promising"],
        counts["maybe"],
        counts["reject"],
        qualified,
        new_qualified,
    )
    return DiscoveryRunResult(
        profile_id=profile.id,
        profile_version=profile.version,
        total_raw=raw_total,
        total_unique=len(all_classified),
        total_qualified=qualified,
        total_new=new_qualified,
        total_excluded=len(excluded),
        items=items,
        excluded_items=excluded,
        source_summaries=source_summaries,
    )


def _sort_classified(items: list[ClassifiedDiscovery]) -> None:
    items.sort(
        key=lambda item: (
            not item.classification.eligible,
            item.classification.role_tier or 99,
            -item.classification.score,
            item.candidate.company_name or "",
            item.candidate.title or "",
        )
    )


def _classification_counts(items: list[ClassifiedDiscovery]) -> dict[str, int]:
    counts = {"promising": 0, "maybe": 0, "reject": 0}
    for item in items:
        counts[item.classification.verdict.value] += 1
    return counts
