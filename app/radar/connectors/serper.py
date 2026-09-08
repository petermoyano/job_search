from __future__ import annotations

import json
from urllib.parse import urlsplit
from urllib.request import Request

from app.radar.connectors.external import (
    OptionalSearchConnector,
    records,
    request_json,
    text,
    valid_url,
)
from app.radar.models import DiscoverySourceKind, RawDiscovery, SearchQuery


class SerperConnector(OptionalSearchConnector):
    name = "serper"
    source_ids = frozenset({name})
    setting_name = "serper_api_key"

    def search(self, query: SearchQuery, limit: int) -> list[RawDiscovery]:
        search_query = f"site:linkedin.com/jobs/view {query.text}"
        payload = request_json(
            Request(
                "https://google.serper.dev/search",
                data=json.dumps({"q": search_query, "num": min(limit, 10)}).encode(),
                headers={
                    "X-API-KEY": self.api_key or "",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
        )
        found = []
        for job in records(payload.get("organic")):
            url = valid_url(job.get("link"))
            if url is None:
                continue
            found.append(
                RawDiscovery(
                    source=DiscoverySourceKind.serper,
                    title=text(job.get("title")),
                    url=url,
                    raw_text=text(job.get("snippet")) or "",
                    metadata={
                        "query": search_query,
                        "query_role_tier": query.role_tier,
                        "source_id": self.name,
                        "origin_domain": urlsplit(str(url)).hostname,
                    },
                )
            )
        return found[:limit]
