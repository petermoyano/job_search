from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode, urlsplit

from app.radar.connectors.base import DiscoveryConnector
from app.radar.connectors.common import get_json, html_to_text, title_may_match_profile
from app.radar.models import (
    DiscoverySourceKind,
    RawDiscovery,
    SearchProfile,
    SearchSource,
)
from app.services.text import normalize_for_matching


JOBSPRESSO_API_URL = "https://jobspresso.co/wp-json/wp/v2/job-listings"
JOBSPRESSO_FIELDS = "id,date_gmt,link,title,content,meta"
JOBSPRESSO_TIMEOUT_SECONDS = 55
JOBSPRESSO_OTHER_ROLES_TYPE_ID = 6
JOBSPRESSO_SEARCH_TERMS = (
    "human resources",
    "talent acquisition",
    "recruiter",
    "people partner",
)


class JobspressoConnector(DiscoveryConnector):
    name = "jobspresso"
    source_ids = frozenset({"jobspresso"})

    def discover(self, profile: SearchProfile, limit: int) -> list[RawDiscovery]:
        source = SearchSource(
            id="jobspresso",
            label="Jobspresso",
            domains=["jobspresso.co"],
            order=1,
        )
        return self.discover_source(profile, source, limit)

    def discover_source(
        self, profile: SearchProfile, source: SearchSource, limit: int
    ) -> list[RawDiscovery]:
        page_size = min(5, max(3, limit))
        urls = [_search_url(term, page_size) for term in JOBSPRESSO_SEARCH_TERMS]
        with ThreadPoolExecutor(max_workers=len(urls)) as pool:
            responses = list(pool.map(_fetch_payload, urls))
        payloads = [response for response in responses if isinstance(response, list)]
        if not payloads:
            error = next(
                (response for response in responses if isinstance(response, RuntimeError)),
                RuntimeError("provider_invalid_payload"),
            )
            raise error
        jobs = sorted(
            (job for payload in payloads for job in payload if isinstance(job, dict)),
            key=lambda job: str(job.get("date_gmt") or ""),
            reverse=True,
        )

        discoveries: list[RawDiscovery] = []
        seen: set[str] = set()
        for job in jobs:
            item = _map_job(job, profile, source)
            if item is None or item.external_id in seen:
                continue
            seen.add(item.external_id or str(item.url))
            discoveries.append(item)
            if len(discoveries) >= limit:
                break
        return discoveries


def _search_url(term: str, page_size: int) -> str:
    params = {
        "per_page": page_size,
        "orderby": "date",
        "order": "desc",
        "job-types": JOBSPRESSO_OTHER_ROLES_TYPE_ID,
        "_fields": JOBSPRESSO_FIELDS,
        "search": term,
    }
    return f"{JOBSPRESSO_API_URL}?{urlencode(params)}"


def _fetch_payload(url: str) -> list | RuntimeError:
    try:
        payload = get_json(url, timeout=JOBSPRESSO_TIMEOUT_SECONDS)
    except RuntimeError as exc:
        return exc
    return payload if isinstance(payload, list) else RuntimeError("provider_invalid_payload")


def _map_job(
    job: object, profile: SearchProfile, source: SearchSource
) -> RawDiscovery | None:
    if not isinstance(job, dict):
        return None
    title = _rendered(job.get("title"))
    provider_url = _text(job.get("link"))
    external_id = _text(job.get("id"))
    if not title or not provider_url or not external_id:
        return None
    if not title_may_match_profile(title, profile.target_roles):
        return None

    meta = job.get("meta") if isinstance(job.get("meta"), dict) else {}
    content = html_to_text(_rendered(job.get("content")) or "")
    filled = _truthy(_meta(meta, "_filled", "filled"))
    application_url = _http_url(
        _meta(meta, "_application", "application", "_application_url")
    ) or provider_url
    location = _text(
        _meta(meta, "_job_location", "job_location", "_location")
    ) or "Remote"
    normalized_location = normalize_for_matching(location)
    worldwide = any(
        term in normalized_location
        for term in ("anywhere", "worldwide", "global", "anywhere in the world")
    )
    generic_remote = normalized_location in {"remote", "remoto", "remota"}
    remote_claim = _truthy(
        _meta(meta, "_remote_position", "remote_position", "_remote")
    ) or "remote" in normalized_location
    salary_min = _positive_number(
        _meta(meta, "_job_salary_min", "_salary_min", "salary_min")
    )
    salary_max = _positive_number(
        _meta(meta, "_job_salary_max", "_salary_max", "salary_max")
    )
    description = (
        f"{content}\nPosition has been filled." if filled else content
    )
    return RawDiscovery(
        source=DiscoverySourceKind.jobspresso,
        title=title,
        company_name=_text(
            _meta(meta, "_company_name", "company_name", "_company")
        ),
        url=provider_url,
        location_text=location,
        raw_text=description,
        external_id=external_id,
        metadata={
            "source_id": source.id,
            "source_label": source.label,
            "acquisition_mode": "jobspresso_wp_rest",
            "attribution_url": provider_url,
            "application_url": application_url,
            "application_text": "Apply" if application_url else None,
            "published_date": _text(job.get("date_gmt")),
            "valid_through": _text(
                _meta(meta, "_job_expires", "job_expires", "_expiry_date")
            ),
            "provider_status": "closed" if filled else "active",
            "provider_remote_claim_trusted": remote_claim,
            "provider_worldwide": worldwide,
            "applicant_locations": (
                [] if worldwide or generic_remote else [location]
            ),
            "employment_type": _text(
                _meta(meta, "_job_type", "job_type", "_employment_type")
            ),
            "salary_min": salary_min,
            "salary_max": salary_max,
            "salary_currency": _text(
                _meta(meta, "_job_salary_currency", "_salary_currency")
            ),
            "salary_period": _text(
                _meta(meta, "_job_salary_unit", "_salary_unit")
            ),
        },
    )


def _meta(meta: dict, *keys: str) -> object:
    for key in keys:
        value = meta.get(key)
        if isinstance(value, list) and value:
            value = value[0]
        if value is not None and value != "":
            return value
    return None


def _rendered(value: object) -> str | None:
    if isinstance(value, dict):
        return _text(value.get("rendered"))
    return _text(value)


def _http_url(value: object) -> str | None:
    text = _text(value)
    if not text:
        return None
    parsed = urlsplit(text)
    return text if parsed.scheme in {"http", "https"} and parsed.netloc else None


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


def _positive_number(value: object) -> int | None:
    try:
        number = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return round(number) if number > 0 else None


def _text(value: object) -> str | None:
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
