from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def new_id() -> str:
    return str(uuid4())


def now_utc() -> datetime:
    return datetime.utcnow()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_utc, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_utc, onupdate=now_utc, nullable=False
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    display_name: Mapped[str | None] = mapped_column(String(255))

    candidate_profiles: Mapped[list[CandidateProfile]] = relationship(
        back_populates="user"
    )


class CandidateProfile(Base, TimestampMixin):
    __tablename__ = "candidate_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_roles: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    preferred_locations: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False
    )
    work_modalities: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False
    )
    seniority: Mapped[str | None] = mapped_column(String(100))
    technical_skills: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False
    )
    ai_skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    languages: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    compensation_preferences: Mapped[dict] = mapped_column(
        JSON, default=dict, nullable=False
    )
    deal_breakers: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    scoring_weights: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    preferred_company_types: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False
    )
    negative_company_types: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False
    )

    user: Mapped[User | None] = relationship(back_populates="candidate_profiles")
    cvs: Mapped[list[CandidateCV]] = relationship(back_populates="candidate_profile")
    job_leads: Mapped[list[JobLead]] = relationship(back_populates="candidate_profile")


class CandidateCV(Base, TimestampMixin):
    __tablename__ = "candidate_cvs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    candidate_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("candidate_profiles.id"), nullable=True
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_profile: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    extraction_method: Mapped[str] = mapped_column(
        String(50), default="deterministic", nullable=False
    )

    candidate_profile: Mapped[CandidateProfile | None] = relationship(
        back_populates="cvs"
    )


class Company(Base, TimestampMixin):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    website: Mapped[str | None] = mapped_column(String(500))
    company_type: Mapped[str | None] = mapped_column(String(100))

    job_leads: Mapped[list[JobLead]] = relationship(back_populates="company")


class JobSource(Base, TimestampMixin):
    __tablename__ = "job_sources"
    __table_args__ = (
        UniqueConstraint("kind", "url", "external_id", name="uq_job_source_identity"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(100), default="manual", nullable=False)
    url: Mapped[str | None] = mapped_column(String(1000))
    external_id: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    job_leads: Mapped[list[JobLead]] = relationship(back_populates="source")


class JobLead(Base, TimestampMixin):
    __tablename__ = "job_leads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    candidate_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("candidate_profiles.id"), nullable=True
    )
    company_id: Mapped[str | None] = mapped_column(
        ForeignKey("companies.id"), nullable=True
    )
    source_id: Mapped[str | None] = mapped_column(
        ForeignKey("job_sources.id"), nullable=True
    )
    title: Mapped[str | None] = mapped_column(String(255))
    company_name: Mapped[str | None] = mapped_column(String(255))
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="new", nullable=False)

    candidate_profile: Mapped[CandidateProfile | None] = relationship(
        back_populates="job_leads"
    )
    company: Mapped[Company | None] = relationship(back_populates="job_leads")
    source: Mapped[JobSource | None] = relationship(back_populates="job_leads")
    analyses: Mapped[list[JobAnalysis]] = relationship(
        back_populates="job_lead", cascade="all, delete-orphan"
    )
    human_decisions: Mapped[list[HumanDecision]] = relationship(
        back_populates="job_lead"
    )


class JobAnalysis(Base, TimestampMixin):
    __tablename__ = "job_analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_lead_id: Mapped[str] = mapped_column(ForeignKey("job_leads.id"), nullable=False)
    facts: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    recommendation: Mapped[str] = mapped_column(String(255), nullable=False)
    recommendation_reason: Mapped[str] = mapped_column(Text, nullable=False)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    audit_trail: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)

    job_lead: Mapped[JobLead] = relationship(back_populates="analyses")
    score_breakdowns: Mapped[list[ScoreBreakdown]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )
    detected_signals: Mapped[list[DetectedSignal]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )
    human_decisions: Mapped[list[HumanDecision]] = relationship(
        back_populates="analysis"
    )


class ScoreBreakdown(Base, TimestampMixin):
    __tablename__ = "score_breakdowns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("job_analyses.id"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    positive_signals: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False
    )
    negative_signals: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False
    )

    analysis: Mapped[JobAnalysis] = relationship(back_populates="score_breakdowns")


class DetectedSignal(Base, TimestampMixin):
    __tablename__ = "detected_signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("job_analyses.id"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    polarity: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text)

    analysis: Mapped[JobAnalysis] = relationship(back_populates="detected_signals")


class HumanDecision(Base, TimestampMixin):
    __tablename__ = "human_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_lead_id: Mapped[str] = mapped_column(ForeignKey("job_leads.id"), nullable=False)
    analysis_id: Mapped[str | None] = mapped_column(
        ForeignKey("job_analyses.id"), nullable=True
    )
    decision: Mapped[str] = mapped_column(String(100), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    job_lead: Mapped[JobLead] = relationship(back_populates="human_decisions")
    analysis: Mapped[JobAnalysis | None] = relationship(
        back_populates="human_decisions"
    )


class RadarRun(Base, TimestampMixin):
    __tablename__ = "radar_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    profile_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    profile_version: Mapped[str] = mapped_column(String(100), nullable=False)
    connector: Mapped[str] = mapped_column(String(100), nullable=False)
    requested_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="completed", nullable=False)
    total_raw: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_unique: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_qualified: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_new: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_excluded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_summaries: Mapped[list[dict]] = mapped_column(
        JSON, default=list, nullable=False
    )
    profile_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    evaluations: Mapped[list["RadarEvaluation"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class RadarProfileConfig(Base, TimestampMixin):
    __tablename__ = "radar_profile_configs"

    profile_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class RadarOpportunity(Base, TimestampMixin):
    __tablename__ = "radar_opportunities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    identity_key: Mapped[str] = mapped_column(String(1000), unique=True, nullable=False)
    canonical_url: Mapped[str] = mapped_column(
        String(1000), unique=True, nullable=False
    )
    source_kind: Mapped[str] = mapped_column(String(100), nullable=False)
    source_domain: Mapped[str | None] = mapped_column(String(255))
    external_id: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(String(500))
    company_name: Mapped[str | None] = mapped_column(String(255))
    location_text: Mapped[str | None] = mapped_column(String(500))
    raw_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    facts: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_utc, nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_utc, nullable=False
    )
    last_presented_at: Mapped[datetime | None] = mapped_column(DateTime)

    evaluations: Mapped[list["RadarEvaluation"]] = relationship(
        back_populates="opportunity", cascade="all, delete-orphan"
    )
    feedback_entries: Mapped[list["RadarFeedback"]] = relationship(
        back_populates="opportunity", cascade="all, delete-orphan"
    )
    deletions: Mapped[list["RadarOpportunityDeletion"]] = relationship(
        back_populates="opportunity", cascade="all, delete-orphan"
    )
    quality_reviews: Mapped[list["RadarQualityReview"]] = relationship(
        back_populates="opportunity", cascade="all, delete-orphan"
    )


class RadarEvaluation(Base, TimestampMixin):
    __tablename__ = "radar_evaluations"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "opportunity_id",
            name="uq_radar_evaluation_run_opportunity",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("radar_runs.id"), nullable=False, index=True
    )
    opportunity_id: Mapped[str] = mapped_column(
        ForeignKey("radar_opportunities.id"), nullable=False, index=True
    )
    verdict: Mapped[str] = mapped_column(String(50), nullable=False)
    eligible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_new: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    presented: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    role_tier: Mapped[int | None] = mapped_column(Integer)
    facts: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    eligibility_checks: Mapped[list[dict]] = mapped_column(
        JSON, default=list, nullable=False
    )
    reasons: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    positive_signals: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False
    )
    negative_signals: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False
    )
    classifier_version: Mapped[str] = mapped_column(String(100), nullable=False)

    run: Mapped[RadarRun] = relationship(back_populates="evaluations")
    opportunity: Mapped[RadarOpportunity] = relationship(back_populates="evaluations")


class RadarFeedback(Base, TimestampMixin):
    __tablename__ = "radar_feedback"
    __table_args__ = (
        UniqueConstraint(
            "opportunity_id",
            "profile_id",
            name="uq_radar_feedback_opportunity_profile",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    opportunity_id: Mapped[str] = mapped_column(
        ForeignKey("radar_opportunities.id"), nullable=False, index=True
    )
    profile_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    opportunity: Mapped[RadarOpportunity] = relationship(
        back_populates="feedback_entries"
    )


class RadarOpportunityDeletion(Base, TimestampMixin):
    __tablename__ = "radar_opportunity_deletions"
    __table_args__ = (
        UniqueConstraint(
            "opportunity_id",
            "profile_id",
            name="uq_radar_opportunity_deletions_opportunity_profile",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    opportunity_id: Mapped[str] = mapped_column(
        ForeignKey("radar_opportunities.id"), nullable=False, index=True
    )
    profile_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    deleted_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_utc, nullable=False
    )

    opportunity: Mapped["RadarOpportunity"] = relationship(back_populates="deletions")


class RadarQualityReview(Base, TimestampMixin):
    """A versioned, persisted quality judgement for a presented opportunity."""

    __tablename__ = "radar_quality_reviews"
    __table_args__ = (
        UniqueConstraint(
            "opportunity_id",
            "profile_id",
            "rubric_version",
            name="uq_radar_quality_review_opportunity_profile_rubric",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    opportunity_id: Mapped[str] = mapped_column(
        ForeignKey("radar_opportunities.id"), nullable=False, index=True
    )
    profile_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("radar_runs.id"), nullable=False, index=True
    )
    rubric_version: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    verdict: Mapped[str | None] = mapped_column(String(10))
    quality_score: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Float)
    rationale: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    risks: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    evidence: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    input_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    opportunity: Mapped[RadarOpportunity] = relationship(
        back_populates="quality_reviews"
    )
    outbox_events: Mapped[list["RadarQualityReviewOutbox"]] = relationship(
        back_populates="review", cascade="all, delete-orphan"
    )


class RadarQualityReviewOutbox(Base, TimestampMixin):
    """Durable SQS delivery intent, written with the review record."""

    __tablename__ = "radar_quality_review_outbox"
    __table_args__ = (
        UniqueConstraint("review_id", name="uq_radar_quality_review_outbox_review"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    review_id: Mapped[str] = mapped_column(
        ForeignKey("radar_quality_reviews.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    delivery_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)

    review: Mapped[RadarQualityReview] = relationship(back_populates="outbox_events")


class AppConfig(Base, TimestampMixin):
    __tablename__ = "app_config"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    value: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
