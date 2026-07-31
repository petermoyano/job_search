from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
import ipaddress
import json
import logging
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from app.radar.models import DiscoverySourceKind, RawDiscovery
from app.services.text import compact_text


LOGGER = logging.getLogger(__name__)
MAX_PAGE_BYTES = 2_000_000
FETCH_TIMEOUT_SECONDS = 12
MAX_JOB_TEXT_CHARS = 60_000
MAX_DISCOVERY_SNIPPET_CHARS = 4_000
USER_AGENT = "JobRadar/1.0 (+manual job opportunity verification)"
APPLY_LABELS = [
    "postular",
    "postúlate",
    "postulate",
    "solicitar empleo",
    "enviar cv",
    "inscribirme",
    "apply",
    "submit application",
]
JSON_LD_PATTERN = re.compile(
    r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    flags=re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class _FetchedPage:
    status: int
    content_type: str
    text: str
    final_url: str


class _PageParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.text_parts: list[str] = []
        self.application_labels: list[str] = []
        self.application_url: str | None = None
        self._ignored_depth = 0
        self._current_link: str | None = None
        self._current_link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._ignored_depth += 1
            return
        attributes = dict(attrs)
        if tag == "a":
            self._current_link = attributes.get("href")
            self._current_link_text = []
        if tag in {"input", "button"}:
            label = attributes.get("value") or attributes.get("aria-label") or ""
            self._record_application(label, attributes.get("formaction"))

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1
            return
        if tag == "a":
            label = compact_text(" ".join(self._current_link_text))
            self._record_application(label, self._current_link)
            self._current_link = None
            self._current_link_text = []

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        cleaned = compact_text(data)
        if not cleaned:
            return
        self.text_parts.append(cleaned)
        if self._current_link is not None:
            self._current_link_text.append(cleaned)

    def _record_application(self, label: str, href: str | None) -> None:
        normalized = label.casefold()
        if not label or not any(term in normalized for term in APPLY_LABELS):
            return
        self.application_labels.append(compact_text(label))
        if href and not self.application_url:
            self.application_url = urljoin(self.base_url, href)


def hydrate_discoveries(
    discoveries: list[RawDiscovery], max_workers: int = 5
) -> list[RawDiscovery]:
    if not discoveries:
        return []
    with ThreadPoolExecutor(
        max_workers=max(1, min(max_workers, len(discoveries)))
    ) as pool:
        return list(pool.map(hydrate_discovery, discoveries))


def hydrate_discovery(discovery: RawDiscovery) -> RawDiscovery:
    if discovery.source != DiscoverySourceKind.tavily:
        return discovery
    url = str(discovery.url)
    if not _is_safe_public_url(url):
        return _failed_copy(discovery, "unsafe_or_unsupported_url")

    try:
        page = _fetch_page(url)
    except HTTPError as exc:
        return discovery.model_copy(
            update={
                "metadata": {
                    **discovery.metadata,
                    "page_fetched": False,
                    "page_http_status": exc.code,
                    "page_fetch_error": f"http_{exc.code}",
                }
            }
        )
    except (URLError, TimeoutError, ValueError, OSError) as exc:
        LOGGER.info("Could not hydrate %s: %s", url, exc)
        return _failed_copy(discovery, type(exc).__name__)

    parser = _PageParser(page.final_url)
    hydrated_text = ""
    application_text = ""
    application_url = None
    structured: dict[str, Any] = {}
    if page.content_type == "text/html":
        parser.feed(page.text)
        hydrated_text = "\n".join(parser.text_parts)
        application_text = "\n".join(dict.fromkeys(parser.application_labels))
        application_url = parser.application_url
        structured = _extract_job_posting(page.text)
        structured_description = _html_to_text(
            str(structured.get("description") or ""), page.final_url
        )
        hydrated_text = _merge_text(hydrated_text, structured_description)
    elif page.content_type.startswith("text/"):
        hydrated_text = page.text

    metadata = {
        **discovery.metadata,
        "page_fetched": True,
        "page_http_status": page.status,
        "page_content_type": page.content_type,
    }
    _copy_structured_metadata(metadata, structured)

    if application_url:
        metadata["application_url"] = application_url
        application_page_text = _fetch_application_text(application_url, page.final_url)
        if application_page_text:
            application_text = application_page_text
            metadata["application_fetched"] = True
        else:
            metadata["application_fetched"] = False
    if application_text:
        metadata["application_text"] = application_text

    structured_company = _nested_name(structured.get("hiringOrganization"))
    structured_location = _structured_location(structured)
    structured_title = _string_value(structured.get("title"))
    if hydrated_text and discovery.raw_text:
        metadata["discovery_snippet"] = discovery.raw_text[:MAX_DISCOVERY_SNIPPET_CHARS]
    company_name = structured_company or discovery.company_name
    location_text = structured_location or discovery.location_text
    title = structured_title or discovery.title
    raw_text = (hydrated_text or discovery.raw_text)[:MAX_JOB_TEXT_CHARS]
    return discovery.model_copy(
        update={
            "title": title,
            "company_name": company_name,
            "location_text": location_text,
            "raw_text": raw_text,
            "metadata": metadata,
        }
    )


def _fetch_page(url: str) -> _FetchedPage:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
        content_type = response.headers.get_content_type()
        charset = response.headers.get_content_charset() or "utf-8"
        body = response.read(MAX_PAGE_BYTES + 1)[:MAX_PAGE_BYTES]
        return _FetchedPage(
            status=getattr(response, "status", 200),
            content_type=content_type,
            text=body.decode(charset, errors="replace"),
            final_url=response.geturl(),
        )


def _fetch_application_text(application_url: str, job_url: str) -> str:
    if not _is_safe_public_url(application_url):
        return ""
    if _without_fragment(application_url) == _without_fragment(job_url):
        return ""
    try:
        page = _fetch_page(application_url)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        return ""
    if page.content_type != "text/html":
        return page.text[:20_000] if page.content_type.startswith("text/") else ""
    parser = _PageParser(page.final_url)
    parser.feed(page.text)
    return "\n".join(parser.text_parts)[:20_000]


def _extract_job_posting(document: str) -> dict[str, Any]:
    for raw_json in JSON_LD_PATTERN.findall(document):
        try:
            payload = json.loads(unescape(raw_json).strip())
        except (json.JSONDecodeError, TypeError):
            continue
        posting = _find_job_posting(payload)
        if posting is not None:
            return posting
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


def _copy_structured_metadata(
    metadata: dict[str, Any], structured: dict[str, Any]
) -> None:
    mappings = {
        "datePosted": "published_date",
        "validThrough": "valid_through",
        "employmentType": "employment_type",
        "jobLocationType": "workplace_type",
    }
    for source_key, target_key in mappings.items():
        value = structured.get(source_key)
        if value and not metadata.get(target_key):
            metadata[target_key] = value
    applicant_locations = _location_names(
        structured.get("applicantLocationRequirements")
    )
    if applicant_locations:
        metadata["applicant_locations"] = applicant_locations


def _structured_location(structured: dict[str, Any]) -> str | None:
    locations = [
        *_location_names(structured.get("applicantLocationRequirements")),
        *_location_names(structured.get("jobLocation")),
    ]
    return ", ".join(dict.fromkeys(locations)) or None


def _location_names(value: Any) -> list[str]:
    if isinstance(value, list):
        return [name for item in value for name in _location_names(item)]
    if not isinstance(value, dict):
        return []
    names: list[str] = []
    name = _string_value(value.get("name"))
    if name:
        names.append(name)
    address = value.get("address")
    if isinstance(address, dict):
        for key in ("addressLocality", "addressRegion", "addressCountry"):
            part = address.get(key)
            if isinstance(part, dict):
                part = part.get("name")
            text = _string_value(part)
            if text:
                names.append(text)
    return names


def _nested_name(value: Any) -> str | None:
    return _string_value(value.get("name")) if isinstance(value, dict) else None


def _html_to_text(value: str, base_url: str) -> str:
    if not value:
        return ""
    parser = _PageParser(base_url)
    parser.feed(value)
    return "\n".join(parser.text_parts)


def _merge_text(original: str, hydrated: str) -> str:
    original = original.strip()
    hydrated = hydrated.strip()
    if not hydrated:
        return original
    if not original:
        return hydrated
    if original in hydrated:
        return hydrated
    if hydrated in original:
        return original
    return f"{original}\n{hydrated}"


def _failed_copy(discovery: RawDiscovery, error: str) -> RawDiscovery:
    return discovery.model_copy(
        update={
            "metadata": {
                **discovery.metadata,
                "page_fetched": False,
                "page_fetch_error": error,
            }
        }
    )


def _without_fragment(url: str) -> str:
    parts = urlsplit(url)
    return parts._replace(fragment="").geturl()


def _string_value(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _is_safe_public_url(url: str) -> bool:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    hostname = parsed.hostname.casefold()
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(
        ".local"
    ):
        return False
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return True
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
    )
