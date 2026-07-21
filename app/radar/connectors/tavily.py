from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from math import ceil
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlsplit
from urllib.request import Request, urlopen

from app.core.config import get_settings
from app.radar.connectors.base import DiscoveryConnector
from app.radar.models import (
    DiscoverySourceKind,
    RawDiscovery,
    SearchProfile,
    SearchQuery,
)


TAVILY_SEARCH_URL = "https://api.tavily.com/search"
LOGGER = logging.getLogger(__name__)
CURATED_RESULT_SHARE = 0.8
DOMAIN_BATCH_SIZE = 5


@dataclass(frozen=True)
class _SearchRequest:
    query: SearchQuery
    max_results: int
    lane: str
    include_domains: tuple[str, ...] = ()
    exclude_domains: tuple[str, ...] = ()


class TavilyConnector(DiscoveryConnector):
    name = "tavily"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or get_settings().tavily_api_key

    def discover(self, profile: SearchProfile, limit: int) -> list[RawDiscovery]:
        if not self.api_key:
            raise RuntimeError("TAVILY_API_KEY is required to use the Tavily connector.")

        discoveries: list[RawDiscovery] = []
        provider_results_total = 0
        accepted_total = 0
        skipped_invalid_total = 0
        search_plan = _build_search_plan(profile, limit)
        for index, search_request in enumerate(search_plan, start=1):
            query = search_request.query
            per_query_limit = search_request.max_results
            if len(discoveries) >= limit:
                break
            LOGGER.info(
                "Tavily query %s/%s: lane=%s max_results=%s query=%r",
                index,
                len(search_plan),
                search_request.lane,
                per_query_limit,
                query.text,
            )
            payload = {
                "api_key": self.api_key,
                "query": query.text,
                "search_depth": "basic",
                "max_results": per_query_limit,
                "include_raw_content": True,
            }
            if search_request.include_domains:
                payload["include_domains"] = list(search_request.include_domains)
            if search_request.exclude_domains:
                payload["exclude_domains"] = list(search_request.exclude_domains)
            data = _post_json(TAVILY_SEARCH_URL, payload)
            results = data.get("results", [])
            provider_results_total += len(results)
            accepted_this_query = 0
            skipped_invalid_this_query = 0
            LOGGER.info("Tavily query returned %s provider result(s)", len(results))
            for item in results:
                url = _normalize_result_url(item.get("url"))
                if not url:
                    skipped_invalid_this_query += 1
                    skipped_invalid_total += 1
                    LOGGER.warning(
                        "Tavily skipped invalid result URL: title=%r url=%r",
                        item.get("title"),
                        item.get("url"),
                    )
                    continue
                raw_text = item.get("raw_content") or item.get("content") or ""
                discoveries.append(
                    RawDiscovery(
                        source=DiscoverySourceKind.tavily,
                        title=item.get("title"),
                        url=url,
                        raw_text=raw_text,
                        metadata={
                            "query": query.text,
                            "search_lane": search_request.lane,
                            "include_domains": list(search_request.include_domains),
                            "exclude_domains": list(search_request.exclude_domains),
                            "score": item.get("score"),
                            "published_date": item.get("published_date"),
                        },
                    )
                )
                accepted_this_query += 1
                accepted_total += 1
                if len(discoveries) >= limit:
                    break
            LOGGER.info(
                "Tavily query summary: query_index=%s provider_results=%s accepted=%s "
                "skipped_invalid_url=%s running_total=%s limit=%s",
                index,
                len(results),
                accepted_this_query,
                skipped_invalid_this_query,
                len(discoveries),
                limit,
            )
        LOGGER.info(
            "Tavily connector summary: profile_id=%s provider_results=%s accepted=%s "
            "skipped_invalid_url=%s returned=%s limit=%s",
            profile.id,
            provider_results_total,
            accepted_total,
            skipped_invalid_total,
            len(discoveries),
            limit,
        )
        return discoveries


def _build_search_plan(
    profile: SearchProfile, limit: int
) -> list[_SearchRequest]:
    if limit <= 0 or not profile.queries:
        return []

    if not profile.preferred_source_domains:
        per_query_limit = min(profile.max_results_per_query, limit)
        return [
            _SearchRequest(
                query=query,
                max_results=per_query_limit,
                lane="general",
                exclude_domains=tuple(profile.excluded_source_domains),
            )
            for query in profile.queries
        ]

    curated_budget = min(limit, ceil(limit * CURATED_RESULT_SHARE))
    domain_batches = _domain_batches(profile.preferred_source_domains)
    batch_budgets = _allocate_budget(curated_budget, len(domain_batches))
    plan = [
        _SearchRequest(
            query=profile.queries[index % len(profile.queries)],
            max_results=min(profile.max_results_per_query, budget),
            lane="curated",
            include_domains=tuple(domain_batch),
        )
        for index, (domain_batch, budget) in enumerate(
            zip(domain_batches, batch_budgets, strict=True)
        )
        if budget > 0
    ]

    exploratory_budget = limit - curated_budget
    if exploratory_budget > 0:
        plan.append(
            _SearchRequest(
                query=profile.queries[len(plan) % len(profile.queries)],
                max_results=min(
                    profile.max_results_per_query, exploratory_budget
                ),
                lane="exploratory",
                exclude_domains=tuple(profile.excluded_source_domains),
            )
        )
    return plan


def _domain_batches(domains: list[str]) -> list[list[str]]:
    return [
        domains[index : index + DOMAIN_BATCH_SIZE]
        for index in range(0, len(domains), DOMAIN_BATCH_SIZE)
    ]


def _allocate_budget(total: int, slots: int) -> list[int]:
    if slots <= 0:
        return []
    base, extra = divmod(total, slots)
    return [base + (1 if index < extra else 0) for index in range(slots)]


def _normalize_result_url(value: str | None) -> str | None:
    if not value:
        return None

    stripped = value.strip()
    if _is_absolute_http_url(stripped):
        return stripped

    parsed = urlsplit(stripped)
    if parsed.path == "/goto":
        nested_values = parse_qs(parsed.query).get("url", [])
        for nested in nested_values:
            decoded = unquote(nested).strip()
            if _is_absolute_http_url(decoded):
                return decoded

    return None


def _is_absolute_http_url(value: str) -> bool:
    parsed = urlsplit(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _post_json(url: str, payload: dict) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Tavily request failed with HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Tavily request failed: {exc.reason}") from exc

