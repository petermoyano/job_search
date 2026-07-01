from __future__ import annotations

import json
import logging
from urllib.error import HTTPError, URLError
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
            LOGGER.info("Tavily query returned %s result(s)", len(results))
            for item in results:
                url = item.get("url")
                if not url:
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
                if len(discoveries) >= limit:
                    break
        return discoveries


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

