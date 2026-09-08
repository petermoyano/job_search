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


class SerpApiGoogleJobsConnector(OptionalSearchConnector):
    name = "serpapi_google_jobs"
    source_ids = frozenset({name})
    setting_name = "serpapi_api_key"

    def search(self, query: SearchQuery, limit: int) -> list[RawDiscovery]:
        params = {
            "engine": "google_jobs",
            "q": query.text,
            "api_key": self.api_key or "",
        }
        payload = request_json(
            Request("https://serpapi.com/search.json?" + urlencode(params))
        )
        found = []
        for job in records(payload.get("jobs_results")):
            links = [
                {"title": text(option.get("title")), "link": str(url)}
                for option in records(job.get("apply_options"))
                if (url := valid_url(option.get("link"))) is not None
            ]
            url = (
                valid_url(links[0]["link"])
                if links
                else valid_url(job.get("share_link"))
            )
            if url is None:
                continue
            extensions = job.get("detected_extensions")
            extensions = extensions if isinstance(extensions, dict) else {}
            found.append(
                RawDiscovery(
                    source=DiscoverySourceKind.serpapi_google_jobs,
                    external_id=text(job.get("job_id")),
                    title=text(job.get("title")),
                    company_name=text(job.get("company_name")),
                    url=url,
                    location_text=text(job.get("location")),
                    raw_text=text(job.get("description")) or "",
                    metadata={
                        "query": query.text,
                        "query_role_tier": query.role_tier,
                        "source_id": self.name,
                        "publisher": text(job.get("via")),
                        "application_url": links[0]["link"] if links else None,
                        "apply_options": links,
                        "posting_age": text(extensions.get("posted_at")),
                        "employment_type": text(extensions.get("schedule_type")),
                        "workplace_type": "remote"
                        if extensions.get("work_from_home") is True
                        else None,
                    },
                )
            )
        return found[:limit]
