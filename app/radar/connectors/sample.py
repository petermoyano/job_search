from __future__ import annotations

from app.radar.connectors.base import DiscoveryConnector
from app.radar.models import DiscoverySourceKind, RawDiscovery, SearchProfile


class SampleConnector(DiscoveryConnector):
    name = "sample"

    def discover(self, profile: SearchProfile, limit: int) -> list[RawDiscovery]:
        samples = [
            RawDiscovery(
                source=DiscoverySourceKind.sample,
                title="Senior Backend Engineer, AI Platform",
                company_name="Acme Product AI",
                url="https://boards.greenhouse.io/acme/jobs/123",
                location_text="Remote - United States",
                raw_text=(
                    "We are hiring a Senior Backend Engineer for our product "
                    "engineering team. You will build our SaaS platform, LLM "
                    "features, RAG pipelines, and agentic workflows. Remote - US."
                ),
                external_id="sample-promising",
            ),
            RawDiscovery(
                source=DiscoverySourceKind.sample,
                title="Python Developer",
                company_name="Global Staff Partners",
                url="https://example.com/jobs/python-developer",
                location_text="Remote",
                raw_text=(
                    "Our client is looking for a Python Developer. This is a "
                    "staff augmentation role for a confidential client with "
                    "rotating consulting engagements."
                ),
                external_id="sample-reject",
            ),
        ]
        return samples[:limit]

