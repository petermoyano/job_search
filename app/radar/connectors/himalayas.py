from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlencode

from app.radar.connectors.base import DiscoveryConnector
from app.radar.connectors.common import get_json, html_to_text, title_may_match_profile
from app.radar.models import (
    DiscoverySourceKind,
    RawDiscovery,
    SearchProfile,
    SearchSource,
)


HIMALAYAS_SEARCH_URL = "https://himalayas.app/jobs/api/search"
ROLE_QUERIES = (
    "HR Business Partner",
    "Talent Acquisition",
    "IT Recruiter",
    "People Partner",
    "Human Resources",
)


class HimalayasConnector(DiscoveryConnector):
    name = "himalayas"
    source_ids = frozenset({"himalayas"})

    def discover(self, profile: SearchProfile, limit: int) -> list[RawDiscovery]:
        source = SearchSource(
            id="himalayas",
            label="Himalayas",
            domains=["himalayas.app"],
            order=1,
        )
        return self.discover_source(profile, source, limit)

    def discover_source(
        self, profile: SearchProfile, source: SearchSource, limit: int
    ) -> list[RawDiscovery]:
        discoveries: list[RawDiscovery] = []
        seen: set[str] = set()
        for query in ROLE_QUERIES:
            if len(discoveries) >= limit:
                break
            params = {
                "q": query,
                "country": "Argentina",
                "sort": "recent",
            }
            url = f"{HIMALAYAS_SEARCH_URL}?{urlencode(params)}"
            payload = get_json(url)
            jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
            for job in jobs:
                item = _map_job(job, profile, source)
                if item is None or item.external_id in seen:
                    continue
                seen.add(item.external_id or str(item.url))
                discoveries.append(item)
                if len(discoveries) >= limit:
                    break
        return discoveries


def _map_job(
    job: object, profile: SearchProfile, source: SearchSource
) -> RawDiscovery | None:
    if not isinstance(job, dict):
        return None
    title = _text(job.get("title"))
    application_url = _text(job.get("applicationLink"))
    guid = _text(job.get("guid"))
    if not title or not application_url or not guid:
        return None
    if not title_may_match_profile(title, profile.target_roles):
        return None

    restrictions = [
        _text(item.get("name"))
        for item in job.get("locationRestrictions", [])
        if isinstance(item, dict) and _text(item.get("name"))
    ]
    worldwide = not restrictions
    salary_min = _positive_number(job.get("minSalary"))
    salary_max = _positive_number(job.get("maxSalary"))
    seniority = job.get("seniority")
    if isinstance(seniority, list):
        seniority_text = ", ".join(str(item) for item in seniority)
    else:
        seniority_text = _text(seniority)
    metadata = {
        "source_id": source.id,
        "source_label": source.label,
        "acquisition_mode": "himalayas_api",
        "attribution_url": application_url,
        "application_url": application_url,
        "published_date": _timestamp(job.get("pubDate")),
        "valid_through": _timestamp(job.get("expiryDate")),
        "provider_status": "active",
        "provider_remote_claim_trusted": True,
        "provider_worldwide": worldwide,
        "applicant_locations": restrictions,
        "seniority": seniority_text,
        "employment_type": _text(job.get("employmentType")),
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": _text(job.get("currency")),
        "salary_period": _text(job.get("salaryPeriod")) or "annual",
        "categories": job.get("categories") or [],
    }
    return RawDiscovery(
        source=DiscoverySourceKind.himalayas,
        title=title,
        company_name=_text(job.get("companyName")),
        url=application_url,
        location_text=", ".join(restrictions) if restrictions else "Worldwide",
        raw_text=html_to_text(_text(job.get("description")) or _text(job.get("excerpt"))),
        external_id=guid,
        metadata=metadata,
    )


def _timestamp(value: object) -> str | None:
    if isinstance(value, (int, float)) and value > 0:
        seconds = value / 1000 if value > 100_000_000_000 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()
    return _text(value)


def _positive_number(value: object) -> int | None:
    return round(value) if isinstance(value, (int, float)) and value > 0 else None


def _text(value: object) -> str | None:
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None

