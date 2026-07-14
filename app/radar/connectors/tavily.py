from __future__ import annotations

import json
import logging
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlsplit
from urllib.request import Request, urlopen

from app.core.config import get_settings
from app.radar.connectors.base import DiscoveryConnector
from app.radar.models import DiscoverySourceKind, RawDiscovery, SearchProfile


TAVILY_SEARCH_URL = "https://api.tavily.com/search"
LOGGER = logging.getLogger(__name__)


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
        per_query_limit = min(profile.max_results_per_query, max(1, limit))
        for index, query in enumerate(profile.queries, start=1):
            if len(discoveries) >= limit:
                break
            LOGGER.info(
                "Tavily query %s/%s: max_results=%s query=%r",
                index,
                len(profile.queries),
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

