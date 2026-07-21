import json
from pathlib import Path

from app.radar.classify import classify_candidate
from app.radar.connectors.sample import SampleConnector
from app.radar.connectors.tavily import TavilyConnector
from app.radar.discovery import run_discovery
from app.radar.models import DiscoverySourceKind, PageType, RadarVerdict, RawDiscovery
from app.radar.normalize import canonicalize_url, normalize_discovery
from app.radar.profiles import (
    PETER_REMOTE_AI_FULLSTACK_PRODUCT,
    PETER_US_REMOTE_DIRECT_PRODUCT,
    ROMINA_EXCLUDED_SOURCE_DOMAINS,
    ROMINA_MENDOZA_HR_ONSITE_HYBRID,
    ROMINA_REMOTE_SPANISH_HR,
    ROMINA_TIER_1_SOURCE_DOMAINS,
    get_profile,
)


def test_sample_discovery_classifies_promising_and_reject() -> None:
    result = run_discovery(
        profile=PETER_US_REMOTE_DIRECT_PRODUCT,
        connectors=[SampleConnector()],
        limit=10,
    )

    assert result.total_raw == 2
    assert result.total_unique == 2
    verdicts = {
        item.candidate.external_id: item.classification.verdict
        for item in result.items
    }
    assert verdicts["sample-promising"] == RadarVerdict.promising
    assert verdicts["sample-reject"] == RadarVerdict.reject


def test_profile_selection_includes_peter_and_romina_profiles() -> None:
    assert get_profile("peter-latam-remote-ai-fullstack-product") == (
        PETER_REMOTE_AI_FULLSTACK_PRODUCT
    )
    assert get_profile("romina-remote-spanish-hr") == ROMINA_REMOTE_SPANISH_HR
    assert get_profile("romina-mendoza-hr-onsite-hybrid") == (
        ROMINA_MENDOZA_HR_ONSITE_HYBRID
    )
    assert PETER_US_REMOTE_DIRECT_PRODUCT == PETER_REMOTE_AI_FULLSTACK_PRODUCT


def test_romina_remote_spanish_hr_role_scores_promising() -> None:
    classification = _classify_text(
        ROMINA_REMOTE_SPANISH_HR,
        title="Analista de Recursos Humanos remoto",
        raw_text="""
        Buscamos Analista de Recursos Humanos para trabajo remoto desde Argentina.
        Tareas de reclutamiento y selección de personal, onboarding, clima laboral
        y seguimiento de KPIs de RRHH. Modalidad remota, español nativo.
        """,
    )

    assert classification.verdict == RadarVerdict.promising
    assert classification.score >= 70


def test_romina_remote_english_required_role_is_rejected() -> None:
    classification = _classify_text(
        ROMINA_REMOTE_SPANISH_HR,
        title="HR Business Partner remoto",
        raw_text="""
        Remote HR Business Partner para LATAM. Requisito excluyente: inglés avanzado
        y experiencia bilingual con equipos internacionales.
        """,
    )

    assert classification.verdict == RadarVerdict.reject
    assert any("required English" in signal for signal in classification.negative_signals)


def test_romina_mendoza_onsite_hrbp_scores_promising() -> None:
    classification = _classify_text(
        ROMINA_MENDOZA_HR_ONSITE_HYBRID,
        title="HR Business Partner Mendoza",
        raw_text="""
        Empresa de Mendoza incorpora HR Business Partner para modalidad híbrido.
        Responsabilidades de recursos humanos, reclutamiento y selección,
        onboarding, clima laboral y acompañamiento a líderes en Gran Mendoza.
        """,
    )

    assert classification.verdict == RadarVerdict.promising
    assert classification.score >= 70


def test_romina_mendoza_buenos_aires_or_relocation_role_is_rejected() -> None:
    classification = _classify_text(
        ROMINA_MENDOZA_HR_ONSITE_HYBRID,
        title="Analista de Recursos Humanos",
        raw_text="""
        Analista de Recursos Humanos para CABA, Buenos Aires. Puesto presencial
        con relocation required. Tareas de reclutamiento y onboarding.
        """,
    )

    assert classification.verdict == RadarVerdict.reject
    assert any(
        "not local to Mendoza" in signal for signal in classification.negative_signals
    )



def test_romina_irrelevant_results_are_rejected_before_fit_scoring() -> None:
    fixture_path = (
        Path(__file__).parent / "fixtures" / "romina_irrelevant_results.json"
    )
    fixtures = json.loads(fixture_path.read_text(encoding="utf-8"))

    for fixture in fixtures:
        candidate = normalize_discovery(
            RawDiscovery(
                source=DiscoverySourceKind.tavily,
                title=fixture["title"],
                url=fixture["url"],
                raw_text=fixture["raw_text"],
            )
        )
        classification = classify_candidate(candidate, ROMINA_REMOTE_SPANISH_HR)

        assert classification.verdict == RadarVerdict.reject, fixture["url"]
        assert classification.score == 0, fixture["url"]
        assert classification.page_type == PageType(fixture["expected_page_type"])
        assert classification.is_job_posting is False


def test_spanish_matching_is_accent_insensitive() -> None:
    accented = _classify_text(
        ROMINA_MENDOZA_HR_ONSITE_HYBRID,
        title="Analista de Recursos Humanos",
        raw_text=(
            "Vacante híbrida en Guaymallén, Mendoza. Responsabilidades de "
            "reclutamiento y selección, inducción y capacitación."
        ),
    )
    unaccented = _classify_text(
        ROMINA_MENDOZA_HR_ONSITE_HYBRID,
        title="Analista de Recursos Humanos",
        raw_text=(
            "Vacante hibrida en Guaymallen, Mendoza. Responsabilidades de "
            "reclutamiento y seleccion, induccion y capacitacion."
        ),
    )

    assert accented.score == unaccented.score
    assert accented.verdict == unaccented.verdict


def test_tavily_connector_normalizes_relative_goto_urls(monkeypatch) -> None:
    def fake_post_json(_url, _payload):
        return {
            "results": [
                {
                    "title": "Redirected HR role",
                    "url": "/goto?url=https%3A%2F%2Fexample.com%2Fjobs%2Fhr-role",
                    "content": "Recursos Humanos Mendoza presencial",
                }
            ]
        }

    monkeypatch.setattr("app.radar.connectors.tavily._post_json", fake_post_json)

    discoveries = TavilyConnector(api_key="test-key").discover(
        ROMINA_MENDOZA_HR_ONSITE_HYBRID, limit=1
    )

    assert len(discoveries) == 1
    assert str(discoveries[0].url) == "https://example.com/jobs/hr-role"


def test_tavily_connector_skips_invalid_relative_urls(monkeypatch) -> None:
    def fake_post_json(_url, _payload):
        return {
            "results": [
                {"title": "Bad redirect", "url": "/goto?url=not-a-url"},
                {
                    "title": "Good result",
                    "url": "https://example.com/jobs/good",
                    "content": "Recursos Humanos Mendoza presencial",
                },
            ]
        }

    monkeypatch.setattr("app.radar.connectors.tavily._post_json", fake_post_json)

    discoveries = TavilyConnector(api_key="test-key").discover(
        ROMINA_MENDOZA_HR_ONSITE_HYBRID, limit=2
    )

    assert discoveries
    assert all(str(item.url) == "https://example.com/jobs/good" for item in discoveries)


def test_tavily_uses_tier_1_domains_and_an_exploratory_lane(monkeypatch) -> None:
    payloads: list[dict] = []

    def fake_post_json(_url, payload):
        payloads.append(payload)
        return {"results": []}

    monkeypatch.setattr("app.radar.connectors.tavily._post_json", fake_post_json)

    TavilyConnector(api_key="test-key").discover(
        ROMINA_REMOTE_SPANISH_HR, limit=25
    )

    curated_payloads = [
        payload for payload in payloads if "include_domains" in payload
    ]
    searched_domains = {
        domain
        for payload in curated_payloads
        for domain in payload["include_domains"]
    }
    exploratory_payloads = [
        payload for payload in payloads if "exclude_domains" in payload
    ]

    assert searched_domains == set(ROMINA_TIER_1_SOURCE_DOMAINS)
    assert all(len(payload["include_domains"]) <= 5 for payload in curated_payloads)
    assert len(exploratory_payloads) == 1
    assert set(exploratory_payloads[0]["exclude_domains"]) == set(
        ROMINA_EXCLUDED_SOURCE_DOMAINS
    )
    assert sum(payload["max_results"] for payload in payloads) == 25


def test_canonicalize_url_removes_tracking_params() -> None:
    url = "https://Jobs.Lever.co/acme/123/?utm_source=linkedin&foo=bar#apply"

    assert canonicalize_url(url) == "https://jobs.lever.co/acme/123?foo=bar"


def _classify_text(profile, title: str, raw_text: str):
    candidate = normalize_discovery(
        RawDiscovery(
            source=DiscoverySourceKind.sample,
            title=title,
            url="https://example.com/jobs/123",
            raw_text=raw_text,
        )
    )
    return classify_candidate(candidate, profile)
