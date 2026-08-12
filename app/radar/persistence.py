from __future__ import annotations

import logging

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import (
    RadarEvaluation,
    RadarFeedback,
    RadarOpportunity,
    RadarRun,
    now_utc,
)
from app.radar.dedupe import candidate_identity_key
from app.radar.models import ClassifiedDiscovery, DiscoveryRunResult, SearchProfile
from app.schemas import RadarFeedbackUpsert


CLASSIFIER_VERSION = "romina-eligibility-v1"
LOGGER = logging.getLogger(__name__)


def load_suppressed_keys(db: Session, profile_id: str) -> set[str]:
    rows = db.execute(
        select(
            RadarOpportunity.identity_key,
            RadarOpportunity.canonical_url,
        )
        .join(
            RadarEvaluation,
            RadarEvaluation.opportunity_id == RadarOpportunity.id,
        )
        .join(RadarRun, RadarRun.id == RadarEvaluation.run_id)
        .where(
            RadarRun.profile_id == profile_id,
            RadarEvaluation.presented.is_(True),
        )
    ).all()
    keys: set[str] = set()
    for identity_key, canonical_url in rows:
        keys.add(identity_key)
        keys.add(f"url:{canonical_url}")
    LOGGER.info(
        "event=radar_suppression_keys_loaded profile_id=%s presented_rows=%s "
        "suppression_keys=%s",
        profile_id,
        len(rows),
        len(keys),
    )
    return keys


def persist_discovery_result(
    db: Session,
    *,
    result: DiscoveryRunResult,
    profile: SearchProfile,
    connector: str,
    requested_limit: int,
) -> RadarRun:
    run = RadarRun(
        profile_id=profile.id,
        profile_version=profile.version,
        connector=connector,
        requested_limit=requested_limit,
        status="completed",
        total_raw=result.total_raw,
        total_unique=result.total_unique,
        total_qualified=result.total_qualified,
        total_new=result.total_new,
        total_excluded=result.total_excluded,
        source_summaries=[
            summary.model_dump(mode="json") for summary in result.source_summaries
        ],
        profile_snapshot=profile.model_dump(mode="json"),
    )
    db.add(run)
    db.flush()
    result.run_id = run.id

    now = now_utc()
    presented_items = {id(item) for item in result.items}
    for item in [*result.items, *result.excluded_items]:
        presented = id(item) in presented_items
        opportunity = _upsert_opportunity(db, item, now=now, presented=presented)
        item.opportunity_id = opportunity.id
        classification = item.classification
        db.add(
            RadarEvaluation(
                run_id=run.id,
                opportunity_id=opportunity.id,
                verdict=classification.verdict.value,
                eligible=classification.eligible,
                is_new=item.is_new,
                presented=presented,
                score=classification.score,
                role_tier=classification.role_tier,
                facts=classification.facts.model_dump(mode="json"),
                eligibility_checks=[
                    check.model_dump(mode="json")
                    for check in classification.eligibility_checks
                ],
                reasons=classification.reasons,
                positive_signals=classification.positive_signals,
                negative_signals=classification.negative_signals,
                classifier_version=CLASSIFIER_VERSION,
            )
        )
    LOGGER.info(
        "event=radar_run_staged run_id=%s profile_id=%s connector=%s "
        "presented=%s excluded=%s evaluations=%s",
        run.id,
        profile.id,
        connector,
        len(result.items),
        len(result.excluded_items),
        len(result.items) + len(result.excluded_items),
    )
    return run


def upsert_feedback(
    db: Session,
    *,
    opportunity: RadarOpportunity,
    payload: RadarFeedbackUpsert,
) -> RadarFeedback:
    feedback = db.scalars(
        select(RadarFeedback).where(
            RadarFeedback.opportunity_id == opportunity.id,
            RadarFeedback.profile_id == payload.profile_id,
        )
    ).first()
    values = {
        "action": payload.action.value,
        "reason_codes": [reason.value for reason in payload.reason_codes],
        "notes": payload.notes,
    }
    operation = "created" if feedback is None else "updated"
    if feedback is None:
        feedback = RadarFeedback(
            opportunity_id=opportunity.id,
            profile_id=payload.profile_id,
            **values,
        )
        db.add(feedback)
    else:
        for key, value in values.items():
            setattr(feedback, key, value)
    db.flush()
    LOGGER.info(
        "event=radar_feedback_staged operation=%s opportunity_id=%s "
        "profile_id=%s action=%s reason_count=%s has_notes=%s",
        operation,
        opportunity.id,
        payload.profile_id,
        payload.action.value,
        len(payload.reason_codes),
        bool(payload.notes),
    )
    return feedback


def list_profile_opportunities(
    db: Session,
    *,
    profile_id: str,
    include_excluded: bool,
    limit: int,
) -> list[dict]:
    statement = (
        select(RadarEvaluation, RadarOpportunity)
        .join(RadarRun, RadarRun.id == RadarEvaluation.run_id)
        .join(
            RadarOpportunity,
            RadarOpportunity.id == RadarEvaluation.opportunity_id,
        )
        .where(RadarRun.profile_id == profile_id)
        .order_by(desc(RadarEvaluation.created_at))
    )
    if not include_excluded:
        statement = statement.where(RadarEvaluation.presented.is_(True))

    rows = db.execute(statement).all()
    output: list[dict] = []
    seen: set[str] = set()
    for evaluation, opportunity in rows:
        if opportunity.id in seen:
            continue
        seen.add(opportunity.id)
        feedback = db.scalars(
            select(RadarFeedback).where(
                RadarFeedback.opportunity_id == opportunity.id,
                RadarFeedback.profile_id == profile_id,
            )
        ).first()
        output.append(
            {
                "id": opportunity.id,
                "canonical_url": opportunity.canonical_url,
                "source_kind": opportunity.source_kind,
                "source_domain": opportunity.source_domain,
                "external_id": opportunity.external_id,
                "title": opportunity.title,
                "company_name": opportunity.company_name,
                "location_text": opportunity.location_text,
                "facts": opportunity.facts,
                "first_seen_at": opportunity.first_seen_at,
                "last_seen_at": opportunity.last_seen_at,
                "last_presented_at": opportunity.last_presented_at,
                "latest_evaluation": {
                    "verdict": evaluation.verdict,
                    "eligible": evaluation.eligible,
                    "is_new": evaluation.is_new,
                    "presented": evaluation.presented,
                    "score": evaluation.score,
                    "role_tier": evaluation.role_tier,
                    "eligibility_checks": evaluation.eligibility_checks,
                    "reasons": evaluation.reasons,
                    "classifier_version": evaluation.classifier_version,
                },
                "feedback": feedback,
            }
        )
        if len(output) >= limit:
            break
    LOGGER.info(
        "event=radar_history_loaded profile_id=%s include_excluded=%s "
        "requested_limit=%s returned=%s",
        profile_id,
        include_excluded,
        limit,
        len(output),
    )
    return output


def _upsert_opportunity(
    db: Session,
    item: ClassifiedDiscovery,
    *,
    now,
    presented: bool,
) -> RadarOpportunity:
    candidate = item.candidate
    identity_key = candidate_identity_key(candidate)
    opportunity = db.scalars(
        select(RadarOpportunity).where(
            RadarOpportunity.canonical_url == candidate.canonical_url
        )
    ).first()
    identity_owner = db.scalars(
        select(RadarOpportunity).where(RadarOpportunity.identity_key == identity_key)
    ).first()
    opportunity = opportunity or identity_owner
    values = {
        "canonical_url": candidate.canonical_url,
        "source_kind": candidate.source.value,
        "source_domain": item.classification.facts.source_domain,
        "external_id": candidate.external_id,
        "title": candidate.title,
        "company_name": candidate.company_name,
        "location_text": candidate.location_text,
        "raw_text": candidate.raw_text,
        "facts": item.classification.facts.model_dump(mode="json"),
        "last_seen_at": now,
    }
    if opportunity is None:
        opportunity = RadarOpportunity(
            identity_key=identity_key,
            first_seen_at=now,
            **values,
        )
        db.add(opportunity)
        db.flush()
    else:
        for key, value in values.items():
            setattr(opportunity, key, value)
        if identity_owner is None or identity_owner.id == opportunity.id:
            opportunity.identity_key = identity_key
    if presented:
        opportunity.last_presented_at = now
    return opportunity
