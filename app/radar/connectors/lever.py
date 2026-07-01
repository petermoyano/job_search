from __future__ import annotations

import json
import logging
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen

from app.radar.connectors.base import DiscoveryConnector
from app.radar.models import DiscoverySourceKind, RawDiscovery, SearchProfile


LOGGER = logging.getLogger(__name__)


class LeverConnector(DiscoveryConnector):
    name = "lever"

    def __init__(self, company_sites: list[str]) -> None:
        self.company_sites = company_sites

    def discover(self, profile: SearchProfile, limit: int) -> list[RawDiscovery]:
        discoveries: list[RawDiscovery] = []
        for company_site in self.company_sites:
            if len(discoveries) >= limit:
                break
            LOGGER.info("Fetching Lever company=%s", company_site)
            url = f"https://api.lever.co/v0/postings/{quote(company_site)}?mode=json"
            data = _get_json(url)
            LOGGER.info("Lever company=%s returned %s posting(s)", company_site, len(data))
            for posting in data:
                hosted_url = posting.get("hostedUrl") or posting.get("applyUrl")
                if not hosted_url:
                    continue
                categories = posting.get("categories") or {}
                raw_text = "\n".join(
                    part
                    for part in [
                        posting.get("descriptionPlain"),
                        posting.get("description"),
                        _lists_to_text(posting.get("lists") or []),
                    ]
                    if part
                )
                discoveries.append(
                    RawDiscovery(
                        source=DiscoverySourceKind.lever,
                        title=posting.get("text"),
                        company_name=company_site,
                        url=hosted_url,
                        location_text=categories.get("location"),
                        raw_text=raw_text,
                        external_id=posting.get("id"),
                        metadata={
                            "company_site": company_site,
                            "team": categories.get("team"),
                            "commitment": categories.get("commitment"),
                            "workplace_type": posting.get("workplaceType"),
                        },
                    )
                )
                if len(discoveries) >= limit:
                    break
        return discoveries


def _lists_to_text(lists: list[dict]) -> str:
    blocks: list[str] = []
    for block in lists:
        content = block.get("content")
        if isinstance(content, str):
            blocks.append(content)
    return "\n".join(blocks)


def _get_json(url: str) -> list[dict]:
    try:
        with urlopen(url, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Lever request failed with HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Lever request failed: {exc.reason}") from exc

