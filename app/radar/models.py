from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class DiscoverySourceKind(StrEnum):
    sample = "sample"
    tavily = "tavily"
    greenhouse = "greenhouse"
    lever = "lever"


class RadarVerdict(StrEnum):
    promising = "promising"
    maybe = "maybe"
    reject = "reject"


class SearchQuery(BaseModel):
    text: str
    reason: str | None = None


class ScoringGroup(BaseModel):
    label: str
    terms: list[str] = Field(default_factory=list)
    points: int = 0


class SearchProfile(BaseModel):
    id: str
    name: str
    description: str
    owner_id: str | None = None
    owner_name: str | None = None
    target_roles: list[str] = Field(default_factory=list)
    location_policy: str
    required_terms: list[str] = Field(default_factory=list)
    preferred_terms: list[str] = Field(default_factory=list)
    reject_terms: list[str] = Field(default_factory=list)
    positive_scoring_groups: list[ScoringGroup] = Field(default_factory=list)
    negative_scoring_groups: list[ScoringGroup] = Field(default_factory=list)
    source_references: list[HttpUrl] = Field(default_factory=list)
    queries: list[SearchQuery] = Field(default_factory=list)
    max_results_per_query: int = 10


class RawDiscovery(BaseModel):
    source: DiscoverySourceKind
    title: str | None = None
    company_name: str | None = None
    url: HttpUrl
    location_text: str | None = None
    raw_text: str = ""
    external_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    discovered_at: datetime = Field(default_factory=datetime.utcnow)


class NormalizedJobCandidate(BaseModel):
    source: DiscoverySourceKind
    title: str | None = None
    company_name: str | None = None
    url: HttpUrl
    canonical_url: str
    location_text: str | None = None
    raw_text: str
    searchable_text: str
    external_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    discovered_at: datetime


class RadarClassification(BaseModel):
    verdict: RadarVerdict
    score: int = Field(ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)
    positive_signals: list[str] = Field(default_factory=list)
    negative_signals: list[str] = Field(default_factory=list)
    needs_review: bool = True


class ClassifiedDiscovery(BaseModel):
    candidate: NormalizedJobCandidate
    classification: RadarClassification


class DiscoveryRunResult(BaseModel):
    profile_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_raw: int
    total_unique: int
    items: list[ClassifiedDiscovery]
