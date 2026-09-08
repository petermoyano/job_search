from __future__ import annotations

from urllib.parse import urlencode
from urllib.request import Request

from app.radar.connectors.external import (
    OptionalSearchConnector,
    records,
    request_json,
    text,
    valid_url,
)
from app.radar.models import DiscoverySourceKind, RawDiscovery, SearchQuery

JSEARCH_HOST = "jsearch.p.rapidapi.com"


class JSearchConnector(OptionalSearchConnector):
    name = "jsearch"
    source_ids = frozenset({name})
    setting_name = "rapidapi_key"

    def search(self, query: SearchQuery, limit: int) -> list[RawDiscovery]:
        params = {"query": query.text, "num_pages": "1"}
        payload = request_json(
            Request(
                f"https://{JSEARCH_HOST}/search-v2?" + urlencode(params),
                headers={
                    "X-RapidAPI-Key": self.api_key or "",
                    "X-RapidAPI-Host": JSEARCH_HOST,
                },
            )
        )
        data = payload.get("data")
        if data is not None and not isinstance(data, dict):
            raise RuntimeError("provider_invalid_response")
        found = []
        for job in records((data or {}).get("jobs")):
            links = [
                {"publisher": text(option.get("publisher")), "apply_link": str(url)}
                for option in records(job.get("apply_options"))
                if (url := valid_url(option.get("apply_link"))) is not None
            ]
            application_url = valid_url(job.get("job_apply_link"))
            if application_url is None and links:
                application_url = valid_url(links[0]["apply_link"])
            url = application_url or valid_url(job.get("job_google_link"))
            if url is None:
                continue
            location = (
                text(job.get("job_location"))
                or ", ".join(
                    value
                    for key in ("job_city", "job_state", "job_country")
                    if (value := text(job.get(key)))
                )
                or None
            )
            found.append(
                RawDiscovery(
                    source=DiscoverySourceKind.jsearch,
                    external_id=text(job.get("job_id")),
                    title=text(job.get("job_title")),
                    company_name=text(job.get("employer_name")),
                    url=url,
                    location_text=location,
                    raw_text=text(job.get("job_description")) or "",
                    metadata={
                        "query": query.text,
                        "query_role_tier": query.role_tier,
                        "source_id": self.name,
                        "publisher": text(job.get("job_publisher")),
                        "application_url": str(application_url)
                        if application_url
                        else None,
                        "apply_options": links,
                        "published_date": text(job.get("job_posted_at_datetime_utc")),
                        "posting_age": text(job.get("job_posted_at")),
                        "employment_type": text(job.get("job_employment_type")),
                        "workplace_type": "remote"
                        if job.get("job_is_remote") is True
                        else None,
                        "country": text(job.get("job_country")),
                    },
                )
            )
        return found[:limit]
