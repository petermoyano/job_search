from __future__ import annotations

import json
from pathlib import Path

from app.radar.classify import classify_candidate
from app.radar.connectors.jobspresso import JobspressoConnector
from app.radar.connectors.randstad_ar import (
    RANDSTAD_HR_URL,
    RandstadArgentinaConnector,
)
from app.radar.models import EligibilityStatus, PageType, RadarVerdict, SearchSource
from app.radar.normalize import normalize_discovery
from app.radar.profiles import ROMINA_REMOTE_SPANISH_HR


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "structured_connector_payloads.json"


def _fixtures() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _source(source_id: str, label: str, domain: str) -> SearchSource:
    return SearchSource(id=source_id, label=label, domains=[domain], order=1)


def _failed_criterion(item, criterion: str) -> bool:
    classification = classify_candidate(normalize_discovery(item), ROMINA_REMOTE_SPANISH_HR)
    return any(
        check.criterion == criterion and check.status == EligibilityStatus.failed
        for check in classification.eligibility_checks
    )


def test_jobspresso_maps_remote_scope_salary_and_closed_status(monkeypatch) -> None:
    payload = _fixtures()["jobspresso"]
    monkeypatch.setattr(
        "app.radar.connectors.jobspresso.get_json",
        lambda _url, timeout: payload,
    )

    discoveries = JobspressoConnector().discover_source(
        ROMINA_REMOTE_SPANISH_HR,
        _source("jobspresso", "Jobspresso", "jobspresso.co"),
        limit=10,
    )

    assert len(discoveries) == 3
    global_job, us_only_job, filled_job = discoveries
    global_classification = classify_candidate(
        normalize_discovery(global_job), ROMINA_REMOTE_SPANISH_HR
    )
    assert global_classification.eligible is True
    assert global_classification.facts.salary_min_usd_monthly == 2000
    assert global_classification.facts.application_url == (
        "https://global-people.example/jobs/hrbp"
    )
    assert _failed_criterion(us_only_job, "hiring_geography")
    filled_classification = classify_candidate(
        normalize_discovery(filled_job), ROMINA_REMOTE_SPANISH_HR
    )
    assert filled_classification.verdict == RadarVerdict.reject
    assert filled_classification.page_type == PageType.expired


def test_randstad_rejects_non_mendoza_and_accepts_mendoza_hybrid(monkeypatch) -> None:
    fixtures = _fixtures()

    def fake_get_bytes(url: str, *, timeout: int) -> bytes:
        assert timeout == 20
        if url == RANDSTAD_HR_URL:
            return fixtures["randstad_listing"].encode()
        external_id = url.rstrip("/").rsplit("_", 1)[-1]
        return fixtures["randstad_details"][external_id].encode()

    monkeypatch.setattr("app.radar.connectors.randstad_ar.get_bytes", fake_get_bytes)

    discoveries = RandstadArgentinaConnector().discover_source(
        ROMINA_REMOTE_SPANISH_HR,
        _source("randstad_ar", "Randstad Argentina", "randstad.com.ar"),
        limit=10,
    )

    assert len(discoveries) == 3
    gba_hybrid, tucuman_onsite, mendoza_hybrid = discoveries
    assert _failed_criterion(gba_hybrid, "work_modality")
    assert _failed_criterion(tucuman_onsite, "work_modality")
    mendoza_classification = classify_candidate(
        normalize_discovery(mendoza_hybrid), ROMINA_REMOTE_SPANISH_HR
    )
    assert mendoza_classification.eligible is True
    assert mendoza_classification.facts.hiring_scope == "mendoza_hybrid"
    assert mendoza_classification.facts.application_url == "https://apply.example/1003"
    assert str(mendoza_hybrid.url).endswith("/trabajos/hrbp_godoy-cruz_1003/")


def test_randstad_reports_invalid_listing_markup(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.radar.connectors.randstad_ar.get_bytes",
        lambda _url, *, timeout: b"<html><body>unexpected response</body></html>",
    )

    connector = RandstadArgentinaConnector()
    source = _source("randstad_ar", "Randstad Argentina", "randstad.com.ar")
    try:
        connector.discover_source(ROMINA_REMOTE_SPANISH_HR, source, limit=10)
    except RuntimeError as exc:
        assert str(exc) == "provider_invalid_html"
    else:
        raise AssertionError("Expected invalid Randstad markup to fail the source")
