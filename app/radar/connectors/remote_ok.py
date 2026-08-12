from __future__ import annotations

from app.radar.connectors.base import DiscoveryConnector
from app.radar.connectors.common import get_json, html_to_text, title_may_match_profile
from app.radar.models import (
    DiscoverySourceKind,
    RawDiscovery,
    SearchProfile,
    SearchSource,
)


REMOTE_OK_API_URL = "https://remoteok.com/api"


class RemoteOkConnector(DiscoveryConnector):
    name = "remote_ok"
    source_ids = frozenset({"remote_ok"})

    def discover(self, profile: SearchProfile, limit: int) -> list[RawDiscovery]:
        source = SearchSource(
            id="remote_ok",
            label="Remote OK",
            domains=["remoteok.com"],
            order=1,
        )
        return self.discover_source(profile, source, limit)

    def discover_source(
        self, profile: SearchProfile, source: SearchSource, limit: int
    ) -> list[RawDiscovery]:
        payload = get_json(REMOTE_OK_API_URL)
        if not isinstance(payload, list):
            raise RuntimeError("provider_invalid_payload")
        discoveries: list[RawDiscovery] = []
        for job in payload:
            item = _map_job(job, profile, source)
            if item is None:
                continue
            discoveries.append(item)
            if len(discoveries) >= limit:
                break
        return discoveries


def _map_job(
    job: object, profile: SearchProfile, source: SearchSource
) -> RawDiscovery | None:
    if not isinstance(job, dict):
        return None
    external_id = _text(job.get("id"))
    title = _text(job.get("position"))
    url = _text(job.get("url")) or _text(job.get("apply_url"))
    if not external_id or not title or not url:
        return None
    if not title_may_match_profile(title, profile.target_roles):
        return None
    salary_min = _positive_number(job.get("salary_min"))
    salary_max = _positive_number(job.get("salary_max"))
    return RawDiscovery(
        source=DiscoverySourceKind.remote_ok,
        title=title,
        company_name=_text(job.get("company")),
        url=url,
        location_text=_text(job.get("location")),
        raw_text=html_to_text(_text(job.get("description"))),
        external_id=external_id,
        metadata={
            "source_id": source.id,
            "source_label": source.label,
            "acquisition_mode": "remote_ok_api",
            "attribution_url": url,
            "application_url": _text(job.get("apply_url")) or url,
            "published_date": _text(job.get("date")),
            "provider_status": "active",
            "salary_min": salary_min,
            "salary_max": salary_max,
            "salary_currency": "USD" if salary_min or salary_max else None,
            "salary_period": "annual",
            "tags": job.get("tags") or [],
        },
    )


def _positive_number(value: object) -> int | None:
    return round(value) if isinstance(value, (int, float)) and value > 0 else None


def _text(value: object) -> str | None:
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None

