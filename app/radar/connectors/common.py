from __future__ import annotations

from html.parser import HTMLParser
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.services.text import compact_text, normalize_for_matching


USER_AGENT = "JobRadar/1.0 (+manual job opportunity search)"


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        cleaned = compact_text(data)
        if cleaned:
            self.parts.append(cleaned)


def html_to_text(value: str) -> str:
    if not value:
        return ""
    parser = _TextParser()
    parser.feed(value)
    return "\n".join(parser.parts)


def get_json(url: str, *, timeout: int = 30) -> Any:
    return json.loads(get_bytes(url, timeout=timeout).decode("utf-8"))


def get_bytes(url: str, *, timeout: int = 30) -> bytes:
    request = Request(
        url,
        headers={
            "Accept": "application/json, application/rss+xml, application/xml, text/xml",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if exc.code == 429:
            raise RuntimeError("provider_rate_limited") from exc
        raise RuntimeError(f"provider_http_{exc.code}: {detail[:300]}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", str(exc))
        raise RuntimeError(f"provider_unavailable: {reason}") from exc


def title_may_match_profile(title: str, target_roles: list[str]) -> bool:
    normalized_title = normalize_for_matching(title)
    if not normalized_title:
        return False
    if any(
        normalize_for_matching(role) in normalized_title
        or normalized_title in normalize_for_matching(role)
        for role in target_roles
    ):
        return True
    broad_terms = [
        "human resources",
        "recursos humanos",
        "people partner",
        "people operations",
        "people experience",
        "talent acquisition",
        "recruiter",
        "reclutador",
        "reclutadora",
        "seleccion",
        "adquisicion de talento",
        "gestion de talento",
        "capital humano",
        "employee experience",
        "employer branding",
        "organizational development",
    ]
    return any(term in normalized_title for term in broad_terms)

