from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SignalPolarity(StrEnum):
    positive = "positive"
    negative = "negative"
    neutral = "neutral"


class HumanDecisionValue(StrEnum):
    discard = "discard"
    save_for_later = "save_for_later"
    investigate_company = "investigate_company"
    apply_directly = "apply_directly"
    contact_hiring_manager = "contact_hiring_manager"
    needs_more_information = "needs_more_information"
    blocked_by_deal_breaker = "blocked_by_deal_breaker"


class SourceInput(BaseModel):
    kind: str = "manual"
    url: str | None = None
    external_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CandidateProfileBase(BaseModel):
    name: str
    target_roles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    work_modalities: list[str] = Field(default_factory=list)
    seniority: str | None = None
    technical_skills: list[str] = Field(default_factory=list)
    ai_skills: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    compensation_preferences: dict[str, Any] = Field(default_factory=dict)
    deal_breakers: list[str] = Field(default_factory=list)
    scoring_weights: dict[str, float] = Field(default_factory=dict)
    preferred_company_types: list[str] = Field(default_factory=list)
    negative_company_types: list[str] = Field(default_factory=list)


class CandidateProfileCreate(CandidateProfileBase):
    user_id: str | None = None


class CandidateProfileRead(CandidateProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str | None = None
    created_at: datetime
    updated_at: datetime


class StructuredCandidateProfile(BaseModel):
    target_roles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    seniority: str | None = None
    technical_skills: list[str] = Field(default_factory=list)
    ai_skills: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    summary: str | None = None


class CandidateCVCreate(BaseModel):
    candidate_profile_id: str | None = None
    raw_text: str = Field(min_length=20)
    use_llm: bool = False


class CandidateCVRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    candidate_profile_id: str | None = None
    raw_text: str
    extracted_profile: dict[str, Any]
    extraction_method: str
    created_at: datetime
    updated_at: datetime


class CVExtractionRequest(BaseModel):
    raw_text: str = Field(min_length=20)
    use_llm: bool = False


class JobLeadCreate(BaseModel):
    candidate_profile_id: str | None = None
    title: str | None = None
    company_name: str | None = None
    raw_text: str = Field(min_length=20)
    source: SourceInput = Field(default_factory=SourceInput)


class AnalyzeJobRequest(JobLeadCreate):
    pass


class JobAnalysisRequest(BaseModel):
    candidate_profile_id: str | None = None


class JobLeadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    candidate_profile_id: str | None = None
    title: str | None = None
    company_name: str | None = None
    raw_text: str
    normalized_text: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class ExtractedJobFacts(BaseModel):
    title: str | None = None
    company_name: str | None = None
    employment_type: str | None = None
    location: str | None = None
    salary_range: str | None = None
    interview_process: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    company_type_guess: str | None = None


class ScoreBreakdownRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    category: str
    score: int
    weight: float
    rationale: str
    positive_signals: list[str]
    negative_signals: list[str]


class DetectedSignalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    category: str
    label: str
    polarity: SignalPolarity
    confidence: float
    evidence: str | None = None


class JobAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_lead_id: str
    facts: dict[str, Any]
    recommendation: str
    recommendation_reason: str
    overall_score: float
    blocked: bool
    audit_trail: list[dict[str, Any]]
    score_breakdowns: list[ScoreBreakdownRead] = Field(default_factory=list)
    detected_signals: list[DetectedSignalRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AnalyzeJobResponse(BaseModel):
    job_lead: JobLeadRead
    analysis: JobAnalysisRead


class HumanDecisionCreate(BaseModel):
    analysis_id: str | None = None
    decision: HumanDecisionValue
    notes: str | None = None


class HumanDecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_lead_id: str
    analysis_id: str | None = None
    decision: HumanDecisionValue
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class RadarFeedbackAction(StrEnum):
    interested = "interested"
    not_relevant = "not_relevant"
    applied = "applied"
    should_have_been_shown = "should_have_been_shown"


class RadarFeedbackReason(StrEnum):
    not_remote = "not_remote"
    cannot_hire_argentina = "cannot_hire_argentina"
    requires_advanced_english = "requires_advanced_english"
    closed = "closed"
    junior_or_internship = "junior_or_internship"
    wrong_role = "wrong_role"
    english_description_or_application = "english_description_or_application"
    duplicate = "duplicate"
    broken_link = "broken_link"
    actually_remote = "actually_remote"
    can_hire_argentina = "can_hire_argentina"
    seniority_matches = "seniority_matches"
    role_matches = "role_matches"
    still_open = "still_open"
    english_not_required = "english_not_required"
    salary_matches = "salary_matches"
    provider_misclassified = "provider_misclassified"
    other = "other"


class RadarFeedbackUpsert(BaseModel):
    profile_id: str
    action: RadarFeedbackAction
    reason_codes: list[RadarFeedbackReason] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_reason_codes(self):
        actions_requiring_reasons = {
            RadarFeedbackAction.not_relevant,
            RadarFeedbackAction.should_have_been_shown,
        }
        if self.action in actions_requiring_reasons and not self.reason_codes:
            raise ValueError("At least one reason is required for this feedback action")
        return self


class RadarFeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    opportunity_id: str
    profile_id: str
    action: RadarFeedbackAction
    reason_codes: list[RadarFeedbackReason]
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class RadarRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    profile_version: str
    connector: str
    requested_limit: int
    status: str
    total_raw: int
    total_unique: int
    total_qualified: int
    total_new: int
    total_excluded: int
    source_summaries: list[dict[str, Any]]
    profile_snapshot: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class RadarOpportunityRead(BaseModel):
    id: str
    profile_id: str
    run_id: str
    profile_version: str
    evaluated_at: datetime
    canonical_url: str
    source_kind: str
    source_domain: str | None = None
    external_id: str | None = None
    title: str | None = None
    company_name: str | None = None
    location_text: str | None = None
    facts: dict[str, Any] = Field(default_factory=dict)
    first_seen_at: datetime
    last_seen_at: datetime
    last_presented_at: datetime | None = None
    latest_evaluation: dict[str, Any] | None = None
    feedback: RadarFeedbackRead | None = None
    quality_review: dict[str, Any] | None = None


class RadarRunRequest(BaseModel):
    profile_id: str
    source: Literal["sample", "configured", "tavily"] = "configured"
    limit: int = Field(default=25, ge=1, le=50)


class ScoringConfigRead(BaseModel):
    default_weights: dict[str, float]
    supported_deal_breakers: list[str]
    recommendation_bands: dict[str, str]
