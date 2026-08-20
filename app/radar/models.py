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
    himalayas = "himalayas"
    remote_ok = "remote_ok"
    we_work_remotely = "we_work_remotely"
    jobspresso = "jobspresso"
    randstad_ar = "randstad_ar"


class AcquisitionMode(StrEnum):
    web_search = "web_search"
    himalayas_api = "himalayas_api"
    remote_ok_api = "remote_ok_api"
    we_work_remotely_rss = "we_work_remotely_rss"
    jobspresso_wp_rest = "jobspresso_wp_rest"
    randstad_html = "randstad_html"


class RadarVerdict(StrEnum):
    promising = "promising"
    maybe = "maybe"
    reject = "reject"


class PageType(StrEnum):
    job_posting = "job_posting"
    job_listing = "job_listing"
    informational = "informational"
    organization_page = "organization_page"
    discussion = "discussion"
    expired = "expired"
    unknown = "unknown"


class EligibilityStatus(StrEnum):
    passed = "pass"
    failed = "fail"
    unknown = "unknown"


class WorkModality(StrEnum):
    remote = "remote"
    hybrid = "hybrid"
    onsite = "onsite"
    unknown = "unknown"


class JobActivityStatus(StrEnum):
    open = "open"
    closed = "closed"
    unknown = "unknown"


class SearchQuery(BaseModel):
    text: str
    reason: str | None = None
    role_tier: int | None = Field(default=None, ge=1, le=3)


class ScoringGroup(BaseModel):
    label: str
    terms: list[str] = Field(default_factory=list)
    points: int = 0


class RoleTier(BaseModel):
    tier: int = Field(ge=1, le=3)
    label: str
    titles: list[str] = Field(default_factory=list)


class SearchSource(BaseModel):
    id: str
    label: str
    domains: list[str] = Field(default_factory=list)
    order: int = Field(ge=1)
    primary: bool = True
    max_results: int = Field(default=5, ge=1, le=20)
    min_qualified_to_stop: int = Field(default=3, ge=1, le=10)
    enabled: bool = True
    acquisition_mode: AcquisitionMode = AcquisitionMode.web_search
    attribution_url: HttpUrl | None = None


class EligibilityPolicy(BaseModel):
    require_fully_remote: bool = False
    eligible_remote_regions: list[str] = Field(default_factory=list)
    allowed_hybrid_locations: list[str] = Field(default_factory=list)
    required_description_language: str | None = None
    require_spanish_application: bool = False
    reject_advanced_english: bool = False
    rejected_seniority_terms: list[str] = Field(default_factory=list)
    excluded_role_terms: list[str] = Field(default_factory=list)
    require_active_posting: bool = False
    minimum_salary_usd_monthly: int | None = Field(default=None, ge=0)


class SearchProfile(BaseModel):
    id: str
    name: str
    description: str
    version: str = "1"
    owner_id: str | None = None
    owner_name: str | None = None
    candidate_summary: str | None = None
    target_roles: list[str] = Field(default_factory=list)
    role_tiers: list[RoleTier] = Field(default_factory=list)
    location_policy: str
    eligibility_policy: EligibilityPolicy | None = None
    required_terms: list[str] = Field(default_factory=list)
    preferred_terms: list[str] = Field(default_factory=list)
    reject_terms: list[str] = Field(default_factory=list)
    positive_scoring_groups: list[ScoringGroup] = Field(default_factory=list)
    negative_scoring_groups: list[ScoringGroup] = Field(default_factory=list)
    source_references: list[HttpUrl] = Field(default_factory=list)
    preferred_source_domains: list[str] = Field(default_factory=list)
    excluded_source_domains: list[str] = Field(default_factory=list)
    ordered_sources: list[SearchSource] = Field(default_factory=list)
    queries: list[SearchQuery] = Field(default_factory=list)
    max_results_per_query: int = 10
    max_qualified_results: int = Field(default=5, ge=1, le=25)


class SearchProfileDocument(BaseModel):
    profile: SearchProfile
    revision: int = Field(ge=0)
    persisted: bool = False


class SearchProfileUpdateRequest(BaseModel):
    profile: SearchProfile
    expected_revision: int = Field(ge=0)


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


class RadarJobFacts(BaseModel):
    source_domain: str | None = None
    description_language: str | None = None
    application_language: str | None = None
    work_modality: WorkModality = WorkModality.unknown
    hiring_scope: str | None = None
    seniority: str | None = None
    activity_status: JobActivityStatus = JobActivityStatus.unknown
    published_at: datetime | None = None
    role_tier: int | None = Field(default=None, ge=1, le=3)
    application_url: str | None = None
    salary_text: str | None = None
    salary_min_usd_monthly: int | None = Field(default=None, ge=0)
    salary_max_usd_monthly: int | None = Field(default=None, ge=0)


class EligibilityCheck(BaseModel):
    criterion: str
    status: EligibilityStatus
    reason: str
    evidence: list[str] = Field(default_factory=list)


class RadarClassification(BaseModel):
    verdict: RadarVerdict
    score: int = Field(ge=0, le=100)
    eligible: bool = False
    page_type: PageType = PageType.unknown
    is_job_posting: bool = False
    reasons: list[str] = Field(default_factory=list)
    positive_signals: list[str] = Field(default_factory=list)
    negative_signals: list[str] = Field(default_factory=list)
    facts: RadarJobFacts = Field(default_factory=RadarJobFacts)
    eligibility_checks: list[EligibilityCheck] = Field(default_factory=list)
    role_tier: int | None = Field(default=None, ge=1, le=3)
    rank_components: dict[str, int] = Field(default_factory=dict)
    needs_review: bool = True


class ClassifiedDiscovery(BaseModel):
    candidate: NormalizedJobCandidate
    classification: RadarClassification
    opportunity_id: str | None = None
    is_new: bool = True


class SourceRunSummary(BaseModel):
    source_id: str
    source_label: str
    raw_count: int = 0
    unique_count: int = 0
    qualified_count: int = 0
    new_qualified_count: int = 0
    excluded_count: int = 0
    continued_to_next: bool = False
    stop_reason: str | None = None
    acquisition_mode: AcquisitionMode = AcquisitionMode.web_search
    status: str = "completed"
    error_code: str | None = None
    duration_ms: int = Field(default=0, ge=0)


class DiscoveryRunResult(BaseModel):
    run_id: str | None = None
    profile_id: str
    profile_version: str = "1"
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_raw: int
    total_unique: int
    total_qualified: int = 0
    total_new: int = 0
    total_excluded: int = 0
    items: list[ClassifiedDiscovery]
    excluded_items: list[ClassifiedDiscovery] = Field(default_factory=list)
    source_summaries: list[SourceRunSummary] = Field(default_factory=list)
