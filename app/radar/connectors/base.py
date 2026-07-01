from __future__ import annotations

from abc import ABC, abstractmethod

from app.radar.models import RawDiscovery, SearchProfile


class DiscoveryConnector(ABC):
    name: str

    @abstractmethod
    def discover(self, profile: SearchProfile, limit: int) -> list[RawDiscovery]:
        """Return raw discoveries for a profile."""

