from __future__ import annotations

from app.radar.models import SearchProfile, SearchQuery


PETER_US_REMOTE_DIRECT_PRODUCT = SearchProfile(
    id="peter-us-remote-direct-product",
    name="Peter - US Remote Direct Product",
    description=(
        "Find remote US-compatible direct employer roles at product companies, "
        "with extra interest in backend, full-stack, platform, product, and AI work."
    ),
    target_roles=[
        "Backend Engineer",
        "Full Stack Engineer",
        "Software Engineer",
        "AI Engineer",
        "Product Engineer",
        "Platform Engineer",
    ],
    location_policy=(
        "Remote role, United States, US time zones, Americas-friendly, or globally "
        "remote with explicit US compatibility."
    ),
    required_terms=["remote"],
    preferred_terms=[
        "United States",
        "US",
        "Americas",
        "product engineering",
        "SaaS",
        "platform",
        "AI",
        "LLM",
        "RAG",
        "agents",
    ],
    reject_terms=[
        "staff augmentation",
        "staffing",
        "agency",
        "consulting",
        "hidden client",
        "confidential client",
        "onsite",
        "hybrid",
        "clearance required",
        "C2C",
    ],
    queries=[
        SearchQuery(
            text='site:boards.greenhouse.io "Backend Engineer" "Remote" "United States"',
            reason="Greenhouse direct company boards for backend roles.",
        ),
        SearchQuery(
            text='site:jobs.lever.co "Software Engineer" "Remote" "United States"',
            reason="Lever direct company boards for software engineering roles.",
        ),
        SearchQuery(
            text='site:ashbyhq.com "Product Engineer" "Remote" "United States"',
            reason="Ashby-hosted direct company boards for product engineering roles.",
        ),
        SearchQuery(
            text='"AI Engineer" "Remote" "United States" "careers"',
            reason="General web discovery for AI roles on company career pages.",
        ),
        SearchQuery(
            text='"Backend Engineer" "Remote - US" "careers"',
            reason="General web discovery for US-remote backend roles.",
        ),
    ],
    max_results_per_query=10,
)


PROFILES = {
    PETER_US_REMOTE_DIRECT_PRODUCT.id: PETER_US_REMOTE_DIRECT_PRODUCT,
}


def get_profile(profile_id: str) -> SearchProfile:
    try:
        return PROFILES[profile_id]
    except KeyError as exc:
        supported = ", ".join(sorted(PROFILES))
        raise ValueError(f"Unknown radar profile '{profile_id}'. Supported: {supported}") from exc

