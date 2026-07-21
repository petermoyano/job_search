from __future__ import annotations

import re
from urllib.parse import urlsplit

from app.radar.models import NormalizedJobCandidate, PageType
from app.services.text import normalize_for_matching


DISCUSSION_DOMAINS = {"reddit.com"}
INFORMATIONAL_DOMAINS = {"wikipedia.org"}

EXPIRED_MARKERS = [
    "job is no longer available",
    "position has been filled",
    "position is no longer available",
    "vacante finalizada",
    "vacante cerrada",
    "oferta finalizada",
    "oferta expirada",
]

LISTING_TITLE_PATTERNS = [
    r"\b\d+\s+(?:empleos|jobs|vacantes|ofertas)\b",
    r"\b(?:empleos|jobs|vacantes|ofertas)\s+(?:de|para|en)\b",
    r"\bresultados?\s+de\s+busqueda\b",
]

LISTING_PATH_PATTERNS = [
    r"/empleo/.*(?:srch|search)",
    r"/(?:jobs|empleos|trabajos|vacantes|ofertas-de-trabajo)/?$",
    r"/(?:job-search|search-jobs|buscar-empleo)/?",
]

INFORMATIONAL_PATH_PATTERNS = [
    r"/wiki/",
    r"/(?:article|articles|blog|insights|resources)/",
]

JOB_POSTING_PATH_PATTERNS = [
    r"/(?:job|jobs|position|positions)/[^/]+",
    r"/(?:empleo|empleos|vacante|vacantes)/[^/]+",
    r"/(?:oferta|ofertas)-(?:de-)?(?:empleo|trabajo)/[^/]+",
]

POSTING_SIGNAL_GROUPS = [
    [
        "we are hiring",
        "we're hiring",
        "estamos buscando",
        "buscamos incorporar",
        "buscamos un",
        "buscamos una",
        "se busca",
    ],
    [
        "requirements",
        "requisitos",
        "qualifications",
        "responsibilities",
        "responsabilidades",
        "tus principales tareas",
    ],
    [
        "apply now",
        "apply for this job",
        "postularme",
        "postulate",
        "enviar cv",
        "solicitar empleo",
    ],
    [
        "modalidad de trabajo",
        "modalidad remota",
        "jornada laboral",
        "tipo de contrato",
        "salary range",
        "rango salarial",
    ],
]


def classify_page_type(candidate: NormalizedJobCandidate) -> PageType:
    """Classify whether a discovery is an individual, active job posting."""
    parsed = urlsplit(candidate.canonical_url)
    domain = _known_domain(parsed.hostname or "")
    path = parsed.path.casefold() or "/"
    title = normalize_for_matching(candidate.title or "")
    text = normalize_for_matching(candidate.searchable_text)

    if _contains_any(text, EXPIRED_MARKERS):
        return PageType.expired
    if domain in DISCUSSION_DOMAINS or path.startswith("/r/"):
        return PageType.discussion
    if domain in INFORMATIONAL_DOMAINS:
        return PageType.informational
    if _matches_any(title, LISTING_TITLE_PATTERNS) or _matches_any(
        path, LISTING_PATH_PATTERNS
    ):
        return PageType.job_listing
    if _matches_any(path, INFORMATIONAL_PATH_PATTERNS):
        return PageType.informational
    if path in {"", "/"}:
        return PageType.organization_page
    if _matches_any(path, JOB_POSTING_PATH_PATTERNS):
        return PageType.job_posting

    signal_groups = sum(
        1 for terms in POSTING_SIGNAL_GROUPS if _contains_any(text, terms)
    )
    if signal_groups >= 2:
        return PageType.job_posting
    return PageType.unknown


def page_type_rejection_reason(page_type: PageType) -> str:
    reasons = {
        PageType.job_listing: (
            "is a job search/listing page, not an individual vacancy"
        ),
        PageType.informational: "is informational content, not a job vacancy",
        PageType.organization_page: (
            "is an organization homepage, not a job vacancy"
        ),
        PageType.discussion: "is discussion content, not a job vacancy",
        PageType.expired: "appears to be an expired or closed vacancy",
        PageType.unknown: "could not be verified as an individual job vacancy",
    }
    return reasons.get(page_type, "is not an eligible job vacancy")


def _matches_any(value: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in patterns)


def _contains_any(value: str, terms: list[str]) -> bool:
    normalized = normalize_for_matching(value)
    return any(normalize_for_matching(term) in normalized for term in terms)


def _known_domain(hostname: str) -> str:
    hostname = hostname.casefold().removeprefix("www.")
    for domain in (*DISCUSSION_DOMAINS, *INFORMATIONAL_DOMAINS):
        if hostname == domain or hostname.endswith(f".{domain}"):
            return domain
    return hostname
