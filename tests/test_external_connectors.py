import io
import json
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

import pytest

from app.radar.connectors import external
from app.radar.connectors.serper import SerperConnector
from app.radar.connectors.serpapi_google_jobs import SerpApiGoogleJobsConnector
from app.radar.connectors.jsearch import JSearchConnector
from app.radar.models import SearchProfile, SearchQuery, SearchSource
from app.radar.normalize import normalize_discovery

CONNECTORS = [SerperConnector, SerpApiGoogleJobsConnector, JSearchConnector]


@pytest.fixture
def profile():
    return SearchProfile(
        id="test",
        name="Test",
        description="Test",
        location_policy="Canada",
        target_roles=["Designer"],
        queries=[SearchQuery(text="Designer Canada", role_tier=2)],
    )


def response(monkeypatch, payload):
    calls = []

    def open_request(request, timeout):
        calls.append(request)
        assert timeout == 15
        return io.BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr(external, "urlopen", open_request)
    return calls


def payload_for(connector, job):
    if connector is SerperConnector:
        return {"organic": [job]}
    if connector is SerpApiGoogleJobsConnector:
        return {"jobs_results": [job]}
    return {"status": "OK", "data": {"jobs": [job], "cursor": "not-followed"}}


@pytest.mark.parametrize("connector", CONNECTORS)
def test_success_normalizes_and_uses_current_request(monkeypatch, profile, connector):
    url = "https://www.linkedin.com/jobs/view/123?utm_source=test"
    job = {
        "title": " Designer ",
        "link": url,
        "snippet": "Design products",
        "job_id": "id-1",
        "company_name": "Acme",
        "location": "Canada",
        "description": "Design products",
        "via": "LinkedIn",
        "apply_options": [
            {
                "title": "LinkedIn",
                "link": url,
                "publisher": "LinkedIn",
                "apply_link": url,
            }
        ],
        "detected_extensions": {
            "posted_at": "2 days ago",
            "schedule_type": "Full-time",
            "work_from_home": True,
        },
        "job_title": " Designer ",
        "employer_name": "Acme",
        "job_location": "Canada",
        "job_description": "Design products",
        "job_apply_link": url,
        "job_publisher": "LinkedIn",
        "job_posted_at_datetime_utc": "2026-09-01T00:00:00Z",
        "job_employment_type": "Full-time",
        "job_is_remote": True,
    }
    calls = response(monkeypatch, payload_for(connector, job))
    raw = connector(api_key="unit-test-key").discover(profile, 3)
    assert len(raw) == len(calls) == 1
    candidate = normalize_discovery(raw[0])
    assert candidate.title == "Designer"
    assert candidate.source.value == connector.name
    assert candidate.canonical_url == "https://www.linkedin.com/jobs/view/123"
    assert candidate.raw_text == "Design products"
    assert candidate.metadata["query_role_tier"] == 2
    request = calls[0]
    params = parse_qs(urlsplit(request.full_url).query)
    if connector is SerperConnector:
        assert request.full_url == "https://google.serper.dev/search"
        assert request.get_header("X-api-key") == "unit-test-key"
        assert (
            json.loads(request.data)["q"]
            == "site:linkedin.com/jobs/view Designer Canada"
        )
        assert candidate.company_name is None
        assert candidate.location_text is None
        assert "published_date" not in candidate.metadata
        assert candidate.metadata["origin_domain"] == "www.linkedin.com"
    else:
        assert candidate.company_name == "Acme"
        assert candidate.location_text == "Canada"
        assert candidate.external_id == "id-1"
        assert candidate.metadata["publisher"] == "LinkedIn"
        assert candidate.metadata["workplace_type"] == "remote"
        assert candidate.metadata["employment_type"] == "Full-time"
        if connector is SerpApiGoogleJobsConnector:
            assert params["engine"] == ["google_jobs"]
            assert params["q"] == ["Designer Canada"]
            assert params["api_key"] == ["unit-test-key"]
            assert candidate.metadata["posting_age"] == "2 days ago"
        else:
            assert urlsplit(request.full_url).path == "/search-v2"
            assert request.get_header("X-rapidapi-host") == "jsearch.p.rapidapi.com"
            assert request.get_header("X-rapidapi-key") == "unit-test-key"
            assert params["query"] == ["Designer Canada"]
            assert params["num_pages"] == ["1"]
            assert candidate.metadata["published_date"] == "2026-09-01T00:00:00Z"


@pytest.mark.parametrize("connector", CONNECTORS)
@pytest.mark.parametrize(
    "payload", [{}, {"organic": [], "jobs_results": [], "data": {"jobs": []}}]
)
def test_empty(monkeypatch, profile, connector, payload):
    response(monkeypatch, payload)
    assert connector(api_key="unit-test-key").discover(profile, 5) == []


@pytest.mark.parametrize("connector", CONNECTORS)
def test_missing_key_skips_http(monkeypatch, profile, connector):
    def forbidden(*args, **kwargs):
        pytest.fail("HTTP must not run without a key")

    monkeypatch.setattr(external, "urlopen", forbidden)
    assert connector(api_key="").discover(profile, 5) == []


@pytest.mark.parametrize("connector", CONNECTORS)
def test_missing_and_malformed_optional_fields(monkeypatch, profile, connector):
    url = "https://example.com/jobs/1"
    job = {
        "link": url,
        "share_link": url,
        "job_apply_link": url,
        "title": {},
        "company_name": [],
        "job_title": 12,
        "detected_extensions": [],
        "apply_options": None,
        "job_city": {},
        "job_is_remote": "true",
    }
    response(monkeypatch, payload_for(connector, job))
    found = connector(api_key="unit-test-key").discover(profile, 2)
    assert len(found) == 1
    candidate = normalize_discovery(found[0])
    assert candidate.title is None and candidate.company_name is None
    assert candidate.location_text is None
    assert candidate.metadata.get("workplace_type") is None


@pytest.mark.parametrize("connector", CONNECTORS)
def test_invalid_urls_and_records_skipped(monkeypatch, profile, connector):
    response(
        monkeypatch,
        payload_for(
            connector, {"link": "bad", "job_apply_link": [], "share_link": "ftp://x"}
        ),
    )
    assert connector(api_key="unit-test-key").discover(profile, 2) == []


@pytest.mark.parametrize("connector", CONNECTORS)
@pytest.mark.parametrize("failure", ["http", "network", "json", "provider"])
def test_failures_are_nonfatal_and_redacted(
    monkeypatch, caplog, profile, connector, failure
):
    def fail(request, timeout):
        if failure == "http":
            raise HTTPError(
                request.full_url, 401, "unit-test-key", {}, io.BytesIO(b"unit-test-key")
            )
        if failure == "network":
            raise URLError("unit-test-key")
        return io.BytesIO(
            b"not-json" if failure == "json" else b'{"error":"unit-test-key"}'
        )

    monkeypatch.setattr(external, "urlopen", fail)
    assert connector(api_key="unit-test-key").discover(profile, 2) == []
    assert "unit-test-key" not in caplog.text
    assert "error=provider_" in caplog.text


@pytest.mark.parametrize("connector", CONNECTORS)
def test_normal_ordered_pipeline_classifies_optional_source(
    monkeypatch, profile, connector
):
    from app.radar.connectors.base import DiscoveryConnector
    from app.radar.discovery import run_discovery
    from app.radar.models import RadarClassification, RadarVerdict

    class Existing(DiscoveryConnector):
        name = "existing"
        source_ids = frozenset({"existing"})

        def discover(self, profile, limit):
            return []

    response(
        monkeypatch,
        payload_for(
            connector,
            {
                "title": "Designer",
                "job_title": "Designer",
                "link": "https://example.com/jobs/1",
                "share_link": "https://example.com/jobs/1",
                "job_apply_link": "https://example.com/jobs/1",
            },
        ),
    )
    classified = []

    def classify(candidate, profile):
        classified.append(candidate)
        return RadarClassification(
            verdict=RadarVerdict.promising, score=80, eligible=True
        )

    monkeypatch.setattr("app.radar.discovery.classify_candidate", classify)
    profile = profile.model_copy(
        update={
            "ordered_sources": [SearchSource(id="existing", label="Existing", order=1)]
        }
    )
    result = run_discovery(
        profile, [Existing(), connector(api_key="unit-test-key")], hydrate=False
    )
    assert len(classified) == len(result.items) == 1
    assert result.items[0].candidate.source.value == connector.name
    assert [s.source_id for s in result.source_summaries] == [
        "existing",
        connector.name,
    ]


def test_configured_registry_and_disabled_startup():
    from fastapi.testclient import TestClient
    from app.api.routes import _radar_connectors_for
    from app.main import app

    connectors = _radar_connectors_for("configured")
    optional = [
        c for c in connectors if isinstance(c, external.OptionalSearchConnector)
    ]
    assert {type(c) for c in optional} == set(CONNECTORS)
    assert all(not c.enabled for c in optional)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200


@pytest.mark.parametrize("connector", CONNECTORS)
def test_profile_fallback_bounded_and_exact_duplicates_removed(
    monkeypatch, profile, connector
):
    url = "https://example.com/jobs/1"
    calls = response(
        monkeypatch,
        payload_for(
            connector,
            {
                "link": url,
                "share_link": url,
                "job_apply_link": url,
            },
        ),
    )
    profile = profile.model_copy(
        update={"queries": [], "target_roles": ["Designer", "Developer", "Writer"]}
    )
    assert len(connector(api_key="unit-test-key").discover(profile, 10)) == 1
    assert len(calls) == 2
    if connector is SerperConnector:
        assert "Designer Canada" in json.loads(calls[0].data)["q"]
    else:
        params = parse_qs(urlsplit(calls[0].full_url).query)
        assert params.get("q", params.get("query")) == ["Designer Canada"]


@pytest.mark.parametrize("connector", CONNECTORS)
def test_excluded_domain_and_disabled_ordered_source(monkeypatch, profile, connector):
    from app.radar.discovery import _connector_for_source, run_discovery

    url = "https://jobs.example.com/jobs/1"
    calls = response(
        monkeypatch,
        payload_for(
            connector,
            {
                "link": url,
                "share_link": url,
                "job_apply_link": url,
            },
        ),
    )
    active = connector(api_key="unit-test-key")
    excluded = profile.model_copy(update={"excluded_source_domains": ["example.com"]})
    assert active.discover(excluded, 5) == []
    calls.clear()
    disabled = profile.model_copy(
        update={
            "ordered_sources": [
                SearchSource(
                    id=connector.name, label="Disabled", order=1, enabled=False
                )
            ]
        }
    )
    assert run_discovery(disabled, [active], hydrate=False).total_raw == 0
    assert calls == []
    assert (
        _connector_for_source(
            [active], SearchSource(id="unrelated", label="Other", order=1)
        )
        is None
    )
