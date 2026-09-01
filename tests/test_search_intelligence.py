from __future__ import annotations

from app.radar.search_intelligence import (
    SearchRunReview,
    SearchRunReviewEvidence,
    run_search_run_review,
)


class StaticSearchIntelligenceModel:
    def invoke(self, input_snapshot):
        assert input_snapshot["run"]["totals"]["qualified"] == 1
        return SearchRunReview(
            alignment_score=82,
            assessment="strong",
            summary="The configured profile and deterministic result agree on the target role.",
            strengths=["The presented role matches the configured target role."],
            gaps=[],
            recommendations=[
                "Compare source-level qualification rates on the next run."
            ],
            evidence=[
                SearchRunReviewEvidence(
                    source="opportunity",
                    detail="The presented opportunity passed the deterministic checks.",
                )
            ],
        )


def test_search_run_review_graph_returns_structured_result() -> None:
    review = run_search_run_review(
        {
            "profile": {"target_roles": ["AI Engineer"]},
            "run": {"totals": {"qualified": 1}},
            "opportunities": [],
        },
        model=StaticSearchIntelligenceModel(),
    )

    assert review.alignment_score == 82
    assert review.assessment == "strong"
    assert review.evidence[0].source == "opportunity"


def test_search_run_review_graph_rejects_incomplete_input() -> None:
    try:
        run_search_run_review(
            {"profile": {}},
            model=StaticSearchIntelligenceModel(),
        )
    except ValueError as exc:
        assert str(exc) == "Search run review input is incomplete"
    else:
        raise AssertionError("Expected incomplete search review input to fail")
