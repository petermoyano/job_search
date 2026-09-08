"""Small shared request/parsing helpers for optional search APIs."""

from __future__ import annotations

import json
import logging
from abc import abstractmethod
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from pydantic import HttpUrl, ValidationError

from app.core.config import get_settings
from app.radar.connectors.base import DiscoveryConnector
from app.radar.models import RawDiscovery, SearchProfile, SearchQuery

LOGGER = logging.getLogger(__name__)


def text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def valid_url(value: object) -> HttpUrl | None:
    value = text(value)
    if value is None:
        return None
    try:
        return HttpUrl(value)
    except ValidationError:
        return None


def records(value: object) -> list[dict[str, Any]]:
    return (
        [item for item in value if isinstance(item, dict)]
        if isinstance(value, list)
        else []
    )


def request_json(request: Request) -> dict[str, Any]:
    # Never include request URLs, response bodies, or exception text in errors:
    # SerpApi authenticates via a query parameter.
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"provider_http_{exc.code}") from None
    except (URLError, TimeoutError, OSError):
        raise RuntimeError("provider_unavailable") from None
    except (ValueError, UnicodeError):
        raise RuntimeError("provider_invalid_json") from None
    if not isinstance(payload, dict):
        raise RuntimeError("provider_invalid_response")
    if payload.get("error") or payload.get("status") in ("ERROR", "FAIL"):
        raise RuntimeError("provider_error")
    return payload


class OptionalSearchConnector(DiscoveryConnector):
    setting_name: str
    supplemental = True

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = (
            getattr(get_settings(), self.setting_name) if api_key is None else api_key
        )

        if not self.enabled:
            LOGGER.info("connector=%s disabled=missing_api_key", self.name)

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def discover(self, profile: SearchProfile, limit: int) -> list[RawDiscovery]:
        if not self.enabled:
            LOGGER.info("connector=%s disabled=missing_api_key", self.name)
            return []
        if limit <= 0:
            return []
        # Existing profiles own rich location-aware queries. Avoid interpreting
        # their prose location_policy as a provider's city/country parameter.
        queries = profile.queries or [
            SearchQuery(text=f"{role} {profile.location_policy}".strip())
            for role in profile.target_roles
        ]
        found: list[RawDiscovery] = []
        seen: set[str] = set()
        for query in queries[:2]:
            if len(found) >= limit:
                break
            try:
                batch = self.search(
                    query, min(limit - len(found), profile.max_results_per_query)
                )
            except RuntimeError as exc:
                LOGGER.warning(
                    "connector=%s query=%r error=%s", self.name, query.text, exc
                )
                continue
            LOGGER.info(
                "connector=%s query=%r returned=%s", self.name, query.text, len(batch)
            )
            for item in batch:
                host = urlsplit(str(item.url)).hostname or ""
                if any(
                    host == domain or host.endswith("." + domain)
                    for domain in (
                        d.lower().removeprefix("www.")
                        for d in profile.excluded_source_domains
                    )
                ):
                    continue
                identity = item.external_id or str(item.url)
                if identity not in seen:
                    seen.add(identity)
                    found.append(item)
                if len(found) >= limit:
                    break
        return found

    @abstractmethod
    def search(self, query: SearchQuery, limit: int) -> list[RawDiscovery]:
        """Make one bounded provider request."""
