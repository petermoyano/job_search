from __future__ import annotations

from app.radar.quality import (
    QualityReviewDecision,
    QualityReviewEvidence,
    run_quality_review,
)


class StaticEvaluator:
    def invoke(self, _input_snapshot):
        return QualityReviewDecision(
            verdict="up",
            quality_score=84,
            confidence=0.88,
            rationale=["Direct role with a clear product scope."],
            risks=["Compensation is not disclosed."],
            evidence=[
                QualityReviewEvidence(
                    source="eligibility_checks",
                    detail="All required deterministic eligibility checks passed.",
                )
            ],
        )


def test_quality_review_graph_returns_a_structured_decision() -> None:
    decision = run_quality_review(
        {
            "profile": {"target_roles": ["AI Engineer"]},
            "opportunity": {
                "title": "AI Product Engineer",
                "raw_text": "Build our product with a direct application path.",
            },
            "evaluation": {
                "eligible": True,
                "score": 91,
                "eligibility_checks": [],
            },
        },
        evaluator=StaticEvaluator(),
    )

    assert decision.verdict == "up"
    assert decision.quality_score == 84
    assert decision.evidence[0].source == "eligibility_checks"


def test_quality_review_graph_rejects_an_incomplete_input() -> None:
    try:
        run_quality_review({"profile": {}}, evaluator=StaticEvaluator())
    except ValueError as exc:
        assert str(exc) == "Quality review input is incomplete"
    else:
        raise AssertionError("Expected an incomplete reviewer input to fail")


def test_only_presented_opportunities_stage_quality_reviews() -> None:
    from app.db.base import Base
    from app.db.session import SessionLocal, engine
    from app.models import RadarQualityReview, RadarQualityReviewOutbox
    from app.radar.connectors.sample import SampleConnector
    from app.radar.discovery import run_discovery
    from app.radar.persistence import persist_discovery_result
    from app.radar.profiles import PETER_REMOTE_AI_FULLSTACK_PRODUCT

    Base.metadata.create_all(bind=engine)
    profile = PETER_REMOTE_AI_FULLSTACK_PRODUCT.model_copy(
        update={
            "id": "quality-review-test-profile",
            "version": "quality-review-test-v1",
        }
    )
    result = run_discovery(profile=profile, connectors=[SampleConnector()], limit=2)

    with SessionLocal() as db:
        persist_discovery_result(
            db,
            result=result,
            profile=profile,
            connector="sample",
            requested_limit=2,
        )
        db.commit()
        reviews = list(
            db.query(RadarQualityReview)
            .filter(RadarQualityReview.profile_id == profile.id)
            .all()
        )
        outbox_events = list(
            db.query(RadarQualityReviewOutbox)
            .join(RadarQualityReview)
            .filter(RadarQualityReview.profile_id == profile.id)
            .all()
        )

    assert len(result.items) == 1
    assert len(result.excluded_items) == 1
    assert len(reviews) == 1
    assert reviews[0].input_snapshot["evaluation"]["eligible"] is True
    assert len(outbox_events) == 1


def test_quality_reviews_can_be_disabled_per_run() -> None:
    from app.db.base import Base
    from app.db.session import SessionLocal, engine
    from app.models import RadarQualityReview, RadarQualityReviewOutbox
    from app.radar.connectors.sample import SampleConnector
    from app.radar.discovery import run_discovery
    from app.radar.persistence import persist_discovery_result
    from app.radar.profiles import PETER_REMOTE_AI_FULLSTACK_PRODUCT

    Base.metadata.create_all(bind=engine)
    profile = PETER_REMOTE_AI_FULLSTACK_PRODUCT.model_copy(
        update={
            "id": "quality-review-disabled-test-profile",
            "version": "quality-review-disabled-test-v1",
        }
    )
    result = run_discovery(profile=profile, connectors=[SampleConnector()], limit=2)

    with SessionLocal() as db:
        persist_discovery_result(
            db,
            result=result,
            profile=profile,
            connector="sample",
            requested_limit=2,
            stage_quality_reviews=False,
        )
        db.commit()
        reviews = list(
            db.query(RadarQualityReview)
            .filter(RadarQualityReview.profile_id == profile.id)
            .all()
        )
        outbox_events = list(
            db.query(RadarQualityReviewOutbox)
            .join(RadarQualityReview)
            .filter(RadarQualityReview.profile_id == profile.id)
            .all()
        )

    assert len(result.items) == 1
    assert len(result.excluded_items) == 1
    assert reviews == []
    assert outbox_events == []
