from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from html import unescape
from html.parser import HTMLParser
import json
import re
from typing import Any
from urllib.parse import urljoin, urlsplit

from app.radar.connectors.base import DiscoveryConnector
from app.radar.connectors.common import get_bytes, html_to_text, title_may_match_profile
from app.radar.models import (
    DiscoverySourceKind,
    RawDiscovery,
    SearchProfile,
    SearchSource,
)
from app.services.text import compact_text, normalize_for_matching


RANDSTAD_HR_URL = "https://www.randstad.com.ar/trabajos/s-recursos-humanos/"
JOB_PATH_PATTERN = re.compile(r"^/trabajos/(?!s-)[^/?#]+_[0-9]+/?$")
JSON_LD_PATTERN = re.compile(
    r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    flags=re.IGNORECASE | re.DOTALL,
)


class RandstadArgentinaConnector(DiscoveryConnector):
    name = "randstad_ar"
    source_ids = frozenset({"randstad_ar"})

    def discover(self, profile: SearchProfile, limit: int) -> list[RawDiscovery]:
        source = SearchSource(
            id="randstad_ar",
            label="Randstad Argentina",
            domains=["randstad.com.ar"],
            order=1,
        )
        return self.discover_source(profile, source, limit)

    def discover_source(
        self, profile: SearchProfile, source: SearchSource, limit: int
    ) -> list[RawDiscovery]:
        listing_document = get_bytes(RANDSTAD_HR_URL, timeout=20).decode(
            "utf-8", errors="replace"
        )
        parser = _JobLinkParser(RANDSTAD_HR_URL)
        parser.feed(listing_document)
        candidate_links = [
            (url, title)
            for url, title in parser.links.items()
            if title_may_match_profile(title, profile.target_roles)
        ]
        if not parser.links:
            match = re.search(
                r"(?<!\d)(\d+)\s+trabajos?\s+encontrados?",
                normalize_for_matching(html_to_text(listing_document)),
            )
            if match and int(match.group(1)) == 0:
                return []
            raise RuntimeError("provider_invalid_html")
        if not candidate_links:
            return []

        fetch_limit = min(20, max(10, limit * 2))
        selected = candidate_links[:fetch_limit]
        with ThreadPoolExecutor(max_workers=min(4, len(selected))) as pool:
            fetched = list(pool.map(_fetch_detail, (url for url, _title in selected)))

        discoveries: list[RawDiscovery] = []
        successful_documents = 0
        for (url, _listing_title), document in zip(selected, fetched, strict=True):
            if document is None:
                continue
            successful_documents += 1
            item = _map_document(url, document, profile, source)
            if item is None:
                continue
            discoveries.append(item)
            if len(discoveries) >= limit:
                break
        if successful_documents == 0:
            raise RuntimeError("provider_details_unavailable")
        if not discoveries:
            raise RuntimeError("provider_invalid_payload")
        return discoveries


class _JobLinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.links: dict[str, str] = {}
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        self._href = dict(attrs).get("href")
        self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            text = compact_text(data)
            if text:
                self._parts.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._href is None:
            return
        url = urljoin(self.base_url, self._href)
        parsed = urlsplit(url)
        title = compact_text(" ".join(self._parts))
        if (
            parsed.hostname
            and parsed.hostname.casefold().endswith("randstad.com.ar")
            and JOB_PATH_PATTERN.match(parsed.path)
            and title
            and url not in self.links
        ):
            self.links[url] = title
        self._href = None
        self._parts = []


class _ApplicationLinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.application_url: str | None = None
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            text = compact_text(data)
            if text:
                self._parts.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._href is None:
            return
        label = normalize_for_matching(" ".join(self._parts))
        if "postular" in label and self.application_url is None:
            self.application_url = urljoin(self.base_url, self._href)
        self._href = None
        self._parts = []


def _fetch_detail(url: str) -> str | None:
    try:
        return get_bytes(url, timeout=20).decode("utf-8", errors="replace")
    except RuntimeError:
        return None


def _map_document(
    url: str,
    document: str,
    profile: SearchProfile,
    source: SearchSource,
) -> RawDiscovery | None:
    posting = _extract_job_posting(document)
    title = _text(posting.get("title"))
    description_html = _text(posting.get("description")) or ""
    if not title or not description_html:
        return None
    if not title_may_match_profile(title, profile.target_roles):
        return None

    link_parser = _ApplicationLinkParser(url)
    link_parser.feed(document)
    application_url = link_parser.application_url or url
    location = _structured_location(posting.get("jobLocation"))
    organization = posting.get("hiringOrganization")
    company = _text(organization.get("name")) if isinstance(organization, dict) else None
    identifier = posting.get("identifier")
    external_id = (
        _text(identifier.get("value")) if isinstance(identifier, dict) else None
    ) or url.rsplit("_", 1)[-1].strip("/")
    salary = _salary_metadata(posting.get("baseSalary"))
    return RawDiscovery(
        source=DiscoverySourceKind.randstad_ar,
        title=title,
        company_name=company,
        url=url,
        location_text=location,
        raw_text=html_to_text(description_html),
        external_id=external_id,
        metadata={
            "source_id": source.id,
            "source_label": source.label,
            "acquisition_mode": "randstad_html",
            "attribution_url": url,
            "application_url": application_url,
            "application_text": "Postularme",
            "published_date": _text(posting.get("datePosted")),
            "valid_through": _text(posting.get("validThrough")),
            "provider_status": "active",
            "employment_type": _text(posting.get("employmentType")),
            "page_fetched": True,
            "page_http_status": 200,
            **salary,
        },
    )


def _extract_job_posting(document: str) -> dict[str, Any]:
    for raw_json in JSON_LD_PATTERN.findall(document):
        try:
            payload = json.loads(unescape(raw_json).strip())
        except (json.JSONDecodeError, TypeError):
            continue
        match = _find_job_posting(payload)
        if match is not None:
            return match
    return {}


def _find_job_posting(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        item_type = value.get("@type")
        types = item_type if isinstance(item_type, list) else [item_type]
        if "JobPosting" in types:
            return value
        for nested in value.values():
            match = _find_job_posting(nested)
            if match is not None:
                return match
    elif isinstance(value, list):
        for nested in value:
            match = _find_job_posting(nested)
            if match is not None:
                return match
    return None


def _structured_location(value: object) -> str | None:
    values = value if isinstance(value, list) else [value]
    parts: list[str] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        address = item.get("address")
        if not isinstance(address, dict):
            continue
        for key in ("addressLocality", "addressRegion", "addressCountry"):
            text = _text(address.get(key))
            if text:
                parts.append(text)
    return ", ".join(dict.fromkeys(parts)) or None


def _salary_metadata(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    quantitative = value.get("value")
    if not isinstance(quantitative, dict):
        return {}
    minimum = _positive_number(quantitative.get("minValue"))
    maximum = _positive_number(quantitative.get("maxValue"))
    if minimum is None and maximum is None:
        return {}
    return {
        "salary_min": minimum,
        "salary_max": maximum,
        "salary_currency": _text(value.get("currency")),
        "salary_period": _text(quantitative.get("unitText")),
    }


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
