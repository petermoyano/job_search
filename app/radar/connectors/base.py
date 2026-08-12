from __future__ import annotations

from abc import ABC, abstractmethod

from app.radar.models import RawDiscovery, SearchProfile, SearchSource


class DiscoveryConnector(ABC):
    name: str
    source_ids: frozenset[str] = frozenset()
    handles_unregistered_sources = False

    @abstractmethod
    def discover(self, profile: SearchProfile, limit: int) -> list[RawDiscovery]:
        """Return raw discoveries for a profile."""


    def discover_source(
        self,
        profile: SearchProfile,
        source: SearchSource,
        limit: int,
    ) -> list[RawDiscovery]:
        return self.discover(profile, min(limit, source.max_results))
