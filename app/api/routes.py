from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.graph.workflow import run_job_analysis_workflow
from app.radar.connectors.sample import SampleConnector
from app.radar.connectors.tavily import TavilyConnector
from app.radar.discovery import run_discovery
from app.radar.models import DiscoveryRunResult, SearchProfile
from app.radar.profiles import PROFILES, get_profile as get_radar_profile
from app.models import (
    CandidateCV,
    CandidateProfile,
    Company,
    DetectedSignal,
    HumanDecision,
    JobAnalysis,
    JobLead,
    JobSource,
    ScoreBreakdown,
)
from app.schemas import (
    AnalyzeJobRequest,
    AnalyzeJobResponse,
    CandidateCVCreate,
    CandidateCVRead,
    CandidateProfileCreate,
    CandidateProfileRead,
    CVExtractionRequest,
    HumanDecisionCreate,
    HumanDecisionRead,
    JobAnalysisRead,
    JobAnalysisRequest,
    JobLeadCreate,
    JobLeadRead,
    RadarRunRequest,
    ScoringConfigRead,
    StructuredCandidateProfile,
)
from app.services.extraction import extract_candidate_profile
from app.services.scoring import DEFAULT_WEIGHTS, SUPPORTED_DEAL_BREAKERS

router = APIRouter()
LOGGER = logging.getLogger(__name__)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/radar/profiles", response_model=list[SearchProfile])
def list_radar_profiles() -> list[SearchProfile]:
    return list(PROFILES.values())


@router.post("/radar/runs", response_model=DiscoveryRunResult)
def run_radar(payload: RadarRunRequest) -> DiscoveryRunResult:
    LOGGER.info(
        "Radar API request received: profile_id=%s source=%s limit=%s",
        payload.profile_id,
        payload.source,
        payload.limit,
    )
    try:
        profile = get_radar_profile(payload.profile_id)
    except ValueError as exc:
        LOGGER.warning("Radar API request rejected: profile_id=%s", payload.profile_id)
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    connectors = [_radar_connector_for(payload.source)]
    try:
        result = run_discovery(profile=profile, connectors=connectors, limit=payload.limit)
    except RuntimeError as exc:
        LOGGER.exception(
            "Radar API run failed: profile_id=%s source=%s", profile.id, payload.source
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    verdict_counts = _radar_verdict_counts(result)
    LOGGER.info(
        "Radar API run completed: profile_id=%s source=%s raw=%s unique=%s items=%s "
        "promising=%s maybe=%s reject=%s",
        result.profile_id,
        payload.source,
        result.total_raw,
        result.total_unique,
        len(result.items),
        verdict_counts["promising"],
        verdict_counts["maybe"],
        verdict_counts["reject"],
    )
    if result.items:
        LOGGER.info(
            "Radar API sample results: %s",
            " | ".join(
                (item.candidate.title or "(untitled)")[:80] for item in result.items[:3]
            ),
        )
    else:
        LOGGER.warning(
            "Radar API returned zero items: profile_id=%s source=%s. "
            "Check connector logs for provider result and skipped URL counts.",
            result.profile_id,
            payload.source,
        )
    return result


@router.post(
    "/profiles",
    response_model=CandidateProfileRead,
    status_code=status.HTTP_201_CREATED,
)
def create_candidate_profile(
    payload: CandidateProfileCreate, db: Session = Depends(get_db)
) -> CandidateProfile:
    profile = CandidateProfile(**payload.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/profiles", response_model=list[CandidateProfileRead])
def list_candidate_profiles(db: Session = Depends(get_db)) -> list[CandidateProfile]:
    return list(
        db.scalars(
            select(CandidateProfile).order_by(desc(CandidateProfile.created_at))
        ).all()
    )


@router.post("/cvs/extract", response_model=StructuredCandidateProfile)
def extract_cv_profile(payload: CVExtractionRequest) -> StructuredCandidateProfile:
    profile, _method = extract_candidate_profile(
        payload.raw_text, use_llm=payload.use_llm
    )
    return profile


@router.post(
    "/cvs", response_model=CandidateCVRead, status_code=status.HTTP_201_CREATED
)
def create_candidate_cv(
    payload: CandidateCVCreate, db: Session = Depends(get_db)
) -> CandidateCV:
    if payload.candidate_profile_id:
        _get_profile(db, payload.candidate_profile_id)
    extracted, method = extract_candidate_profile(
        payload.raw_text, use_llm=payload.use_llm
    )
    cv = CandidateCV(
        candidate_profile_id=payload.candidate_profile_id,
        raw_text=payload.raw_text,
        extracted_profile=extracted.model_dump(),
        extraction_method=method,
    )
    db.add(cv)
    db.commit()
    db.refresh(cv)
    return cv


@router.post("/jobs", response_model=JobLeadRead, status_code=status.HTTP_201_CREATED)
def create_job_lead(payload: JobLeadCreate, db: Session = Depends(get_db)) -> JobLead:
    if payload.candidate_profile_id:
        _get_profile(db, payload.candidate_profile_id)
    job = _create_job_lead(db, payload)
    db.commit()
    db.refresh(job)
    return job


@router.get("/jobs", response_model=list[JobLeadRead])
def list_job_leads(db: Session = Depends(get_db)) -> list[JobLead]:
    return list(db.scalars(select(JobLead).order_by(desc(JobLead.created_at))).all())


@router.post(
    "/jobs/analyze",
    response_model=AnalyzeJobResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_and_analyze_job(
    payload: AnalyzeJobRequest, db: Session = Depends(get_db)
) -> AnalyzeJobResponse:
    if payload.candidate_profile_id:
        _get_profile(db, payload.candidate_profile_id)
    job = _create_job_lead(db, payload)
    db.flush()
    analysis = _run_and_persist_analysis(db, job, payload.candidate_profile_id)
    db.commit()
    job = _get_job(db, job.id)
    analysis = _get_analysis(db, analysis.id)
    return AnalyzeJobResponse(
        job_lead=JobLeadRead.model_validate(job),
        analysis=JobAnalysisRead.model_validate(analysis),
    )


@router.post("/jobs/{job_id}/analyze", response_model=JobAnalysisRead)
def analyze_existing_job(
    job_id: str, payload: JobAnalysisRequest, db: Session = Depends(get_db)
) -> JobAnalysis:
    job = _get_job(db, job_id)
    candidate_profile_id = payload.candidate_profile_id or job.candidate_profile_id
    if candidate_profile_id:
        _get_profile(db, candidate_profile_id)
        job.candidate_profile_id = candidate_profile_id
    analysis = _run_and_persist_analysis(db, job, candidate_profile_id)
    db.commit()
    return _get_analysis(db, analysis.id)


@router.get("/jobs/{job_id}/analysis", response_model=JobAnalysisRead)
def get_latest_job_analysis(job_id: str, db: Session = Depends(get_db)) -> JobAnalysis:
    _get_job(db, job_id)
    analysis = db.scalars(
        select(JobAnalysis)
        .where(JobAnalysis.job_lead_id == job_id)
        .options(
            selectinload(JobAnalysis.score_breakdowns),
            selectinload(JobAnalysis.detected_signals),
        )
        .order_by(desc(JobAnalysis.created_at))
    ).first()
    if analysis is None:
        raise HTTPException(status_code=404, detail="No analysis found for this job")
    return analysis


@router.get("/analyses", response_model=list[JobAnalysisRead])
def list_analyses(db: Session = Depends(get_db)) -> list[JobAnalysis]:
    return list(
        db.scalars(
            select(JobAnalysis)
            .options(
                selectinload(JobAnalysis.score_breakdowns),
                selectinload(JobAnalysis.detected_signals),
            )
            .order_by(desc(JobAnalysis.created_at))
        ).all()
    )


@router.post(
    "/jobs/{job_id}/decisions",
    response_model=HumanDecisionRead,
    status_code=status.HTTP_201_CREATED,
)
def save_human_decision(
    job_id: str, payload: HumanDecisionCreate, db: Session = Depends(get_db)
) -> HumanDecision:
    _get_job(db, job_id)
    if payload.analysis_id:
        analysis = _get_analysis(db, payload.analysis_id)
        if analysis.job_lead_id != job_id:
            raise HTTPException(
                status_code=400, detail="Analysis does not belong to this job"
            )
    decision = HumanDecision(
        job_lead_id=job_id,
        analysis_id=payload.analysis_id,
        decision=payload.decision.value,
        notes=payload.notes,
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)
    return decision


@router.get("/config/scoring", response_model=ScoringConfigRead)
def get_scoring_config() -> ScoringConfigRead:
    return ScoringConfigRead(
        default_weights=DEFAULT_WEIGHTS,
        supported_deal_breakers=SUPPORTED_DEAL_BREAKERS,
        recommendation_bands={
            "80+": "Strong fit",
            "70-79": "Investigate company first",
            "50-69": "Request more information",
            "<50": "Low priority unless new evidence appears",
        },
    )


def _radar_verdict_counts(result: DiscoveryRunResult) -> dict[str, int]:
    counts = {"promising": 0, "maybe": 0, "reject": 0}
    for item in result.items:
        counts[item.classification.verdict.value] += 1
    return counts


def _radar_connector_for(source: str):
    if source == "sample":
        return SampleConnector()
    if source == "tavily":
        return TavilyConnector()
    raise HTTPException(status_code=400, detail=f"Unsupported radar source: {source}")


def _create_job_lead(db: Session, payload: JobLeadCreate) -> JobLead:
    source = JobSource(
        kind=payload.source.kind,
        url=payload.source.url,
        external_id=payload.source.external_id,
        metadata_json=payload.source.metadata,
    )
    db.add(source)
    company = None
    if payload.company_name:
        company = db.scalars(
            select(Company).where(Company.name == payload.company_name)
        ).first()
        if company is None:
            company = Company(name=payload.company_name)
            db.add(company)
    job = JobLead(
        candidate_profile_id=payload.candidate_profile_id,
        company=company,
        source=source,
        title=payload.title,
        company_name=payload.company_name,
        raw_text=payload.raw_text,
        status="new",
    )
    db.add(job)
    return job


def _run_and_persist_analysis(
    db: Session, job: JobLead, candidate_profile_id: str | None
) -> JobAnalysis:
    candidate_profile = (
        _get_profile(db, candidate_profile_id) if candidate_profile_id else None
    )
    state = run_job_analysis_workflow(
        raw_job_text=job.raw_text,
        candidate_profile=candidate_profile,
        title=job.title,
        company_name=job.company_name,
        source_metadata={"job_id": job.id},
    )
    facts = state["facts"]
    result = state["scoring_result"]
    job.normalized_text = state["normalized_job_text"]
    job.status = "analyzed"
    if not job.title and facts.title:
        job.title = facts.title
    if not job.company_name and facts.company_name:
        job.company_name = facts.company_name
    analysis = JobAnalysis(
        job_lead=job,
        facts=facts.model_dump(),
        recommendation=result.recommendation,
        recommendation_reason=result.recommendation_reason,
        overall_score=result.overall_score,
        blocked=result.blocked,
        audit_trail=[
            *state["audit_trail"],
            {
                "node": "PersistDecision",
                "summary": "Analysis persisted; awaiting explicit human decision.",
            },
        ],
    )
    db.add(analysis)
    db.flush()
    for line in result.score_lines:
        db.add(
            ScoreBreakdown(
                analysis_id=analysis.id,
                category=line.category,
                score=line.score,
                weight=line.weight,
                rationale=line.rationale,
                positive_signals=line.positive_signals,
                negative_signals=line.negative_signals,
            )
        )
    for signal in result.signals:
        db.add(
            DetectedSignal(
                analysis_id=analysis.id,
                category=signal.category,
                label=signal.label,
                polarity=signal.polarity,
                confidence=signal.confidence,
                evidence=signal.evidence,
            )
        )
    return analysis


def _get_profile(db: Session, profile_id: str) -> CandidateProfile:
    profile = db.get(CandidateProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Candidate profile not found")
    return profile


def _get_job(db: Session, job_id: str) -> JobLead:
    job = db.get(JobLead, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job lead not found")
    return job


def _get_analysis(db: Session, analysis_id: str) -> JobAnalysis:
    analysis = db.scalars(
        select(JobAnalysis)
        .where(JobAnalysis.id == analysis_id)
        .options(
            selectinload(JobAnalysis.score_breakdowns),
            selectinload(JobAnalysis.detected_signals),
        )
    ).first()
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis
