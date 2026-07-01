from __future__ import annotations

from app.radar.models import SearchProfile, SearchQuery


PETER_REMOTE_AI_FULLSTACK_PRODUCT = SearchProfile(
    id="peter-latam-remote-ai-fullstack-product",
    name="Peter - Remote AI / Full-Stack Product",
    description=(
        "Find fully remote, LATAM-friendly or globally remote direct employer roles "
        "with US-market compensation potential. Prioritize AI Engineer, Applied AI, "
        "full-stack product engineering, and ownership-heavy roles over backend-only work."
    ),
    target_roles=[
        "AI Engineer",
        "Applied AI Engineer",
        "Full-Stack AI Engineer",
        "Full Stack Engineer",
        "Full-stack Developer",
        "AI Product Engineer",
        "Product Engineer",
        "LLM Engineer",
        "RAG Engineer",
        "Software Engineer, AI",
        "Founding Engineer",
        "Forward Deployed Engineer",
    ],
    location_policy=(
        "Fully remote role that is open to Argentina, LATAM, Americas, global remote, "
        "or anywhere candidates. US-based companies are preferred for compensation, "
        "but the role should not require US residency."
    ),
    required_terms=["remote"],
    preferred_terms=[
        "LATAM",
        "Latin America",
        "Argentina",
        "Americas",
        "global remote",
        "anywhere",
        "worldwide",
        "US time zones",
        "AI Engineer",
        "Applied AI",
        "LLM",
        "RAG",
        "agents",
        "function calling",
        "tool calling",
        "LangChain",
        "LlamaIndex",
        "OpenAI",
        "Hugging Face",
        "fine-tuning",
        "Next.js",
        "React",
        "Node.js",
        "TypeScript",
        "Python",
        "product engineering",
        "full ownership",
        "end-to-end",
        "0 to 1",
        "SaaS",
    ],
    reject_terms=[
        "staff augmentation",
        "staffing",
        "agency",
        "hidden client",
        "confidential client",
        "onsite",
        "on-site",
        "hybrid",
        "clearance required",
        "C2C",
        "US only",
        "U.S. only",
        "United States only",
        "must be based in the US",
        "must be located in the US",
        "must reside in the US",
        "US work authorization required",
        "requires US work authorization",
        "sponsorship not available",
    ],
    queries=[
        SearchQuery(
            text='site:jobs.lever.co "AI Engineer" "Remote" "LATAM"',
            reason="Lever roles explicitly mentioning AI, remote work, and LATAM.",
        ),
        SearchQuery(
            text='site:boards.greenhouse.io "Applied AI Engineer" "Remote" "Americas"',
            reason="Greenhouse roles for applied AI that are Americas-friendly.",
        ),
        SearchQuery(
            text='site:jobs.ashbyhq.com "Full-Stack AI Engineer" "Remote"',
            reason="Ashby roles combining full-stack product work and AI engineering.",
        ),
        SearchQuery(
            text='"AI Product Engineer" "Remote" "Latin America" "careers"',
            reason="General web discovery for AI product roles open to Latin America.",
        ),
        SearchQuery(
            text='"Full Stack Engineer" "AI" "Remote" "Americas" "careers"',
            reason="Full-stack AI/product roles compatible with Americas time zones.",
        ),
        SearchQuery(
            text='"Founding Engineer" "AI" "Remote" "LATAM"',
            reason="Ownership-heavy early product engineering roles with AI focus.",
        ),
        SearchQuery(
            text='"LLM Engineer" "Remote" "Argentina"',
            reason="LLM roles explicitly open to Argentina-based candidates.",
        ),
    ],
    max_results_per_query=8,
)

# Backwards-compatible alias for imports/tests that still use the original name.
PETER_US_REMOTE_DIRECT_PRODUCT = PETER_REMOTE_AI_FULLSTACK_PRODUCT


PROFILES = {
    PETER_REMOTE_AI_FULLSTACK_PRODUCT.id: PETER_REMOTE_AI_FULLSTACK_PRODUCT,
}


def get_profile(profile_id: str) -> SearchProfile:
    try:
        return PROFILES[profile_id]
    except KeyError as exc:
        supported = ", ".join(sorted(PROFILES))
        raise ValueError(f"Unknown radar profile '{profile_id}'. Supported: {supported}") from exc
