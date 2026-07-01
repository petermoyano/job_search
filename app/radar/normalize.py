from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.radar.models import NormalizedJobCandidate, RawDiscovery
from app.services.text import normalize_text


TRACKING_PARAMS = {
    "gh_src",
    "lever-source",
    "source",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}


def normalize_discovery(raw: RawDiscovery) -> NormalizedJobCandidate:
    raw_text = raw.raw_text.strip()
    searchable_text = normalize_text(
        "\n".join(
            part
            for part in [
                raw.title,
                raw.company_name,
                raw.location_text,
                raw_text,
            ]
            if part
        )
    )
    return NormalizedJobCandidate(
        source=raw.source,
        title=_clean_optional(raw.title),
        company_name=_clean_optional(raw.company_name),
        url=raw.url,
        canonical_url=canonicalize_url(str(raw.url)),
        location_text=_clean_optional(raw.location_text),
        raw_text=raw_text,
        searchable_text=searchable_text,
        external_id=raw.external_id,
        metadata=raw.metadata,
        discovered_at=raw.discovered_at,
    )


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url)
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key.lower() not in TRACKING_PARAMS
        ]
    )
    normalized_path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            normalized_path,
            query,
            "",
        )
    )


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None

