from __future__ import annotations

import json
import logging
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen

from app.radar.connectors.base import DiscoveryConnector
from app.radar.models import DiscoverySourceKind, RawDiscovery, SearchProfile


LOGGER = logging.getLogger(__name__)


class GreenhouseConnector(DiscoveryConnector):
    name = "greenhouse"

    def __init__(self, board_tokens: list[str]) -> None:
        self.board_tokens = board_tokens

    def discover(self, profile: SearchProfile, limit: int) -> list[RawDiscovery]:
        discoveries: list[RawDiscovery] = []
        for board_token in self.board_tokens:
            if len(discoveries) >= limit:
                break
            LOGGER.info("Fetching Greenhouse board=%s", board_token)
            url = (
                "https://boards-api.greenhouse.io/v1/boards/"
                f"{quote(board_token)}/jobs?content=true"
            )
            data = _get_json(url)
            jobs = data.get("jobs", [])
            LOGGER.info(
                "Greenhouse board=%s returned %s job(s)", board_token, len(jobs)
            )
            for job in jobs:
                absolute_url = job.get("absolute_url")
                if not absolute_url:
                    continue
                offices = job.get("offices") or []
                location_text = ", ".join(
                    office.get("name", "") for office in offices if office.get("name")
                )
                discoveries.append(
                    RawDiscovery(
                        source=DiscoverySourceKind.greenhouse,
                        title=job.get("title"),
                        company_name=board_token,
                        url=absolute_url,
                        location_text=location_text or None,
                        raw_text=job.get("content") or "",
                        external_id=str(job.get("id")) if job.get("id") else None,
                        metadata={"board_token": board_token},
                    )
                )
                if len(discoveries) >= limit:
                    break
        return discoveries


def _get_json(url: str) -> dict:
    try:
        with urlopen(url, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Greenhouse request failed with HTTP {exc.code}: {detail}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"Greenhouse request failed: {exc.reason}") from exc

