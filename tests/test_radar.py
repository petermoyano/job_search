import json
from pathlib import Path

from app.radar.classify import classify_candidate
from app.radar.connectors.base import DiscoveryConnector
from app.radar.connectors.common import title_may_match_profile
from app.radar.connectors.himalayas import _timestamp
from app.radar.connectors.sample import SampleConnector
from app.radar.connectors.tavily import TavilyConnector
from app.radar.discovery import run_discovery
from app.radar.models import (
    AcquisitionMode,
    DiscoverySourceKind,
    EligibilityStatus,
    PageType,
    RadarVerdict,
    RawDiscovery,
    SearchSource,
)
from app.radar.normalize import canonicalize_url, normalize_discovery
from app.radar.profile_store import _upgrade_legacy_sources
from app.radar.profiles import (
    PETER_REMOTE_AI_FULLSTACK_PRODUCT,
    PETER_US_REMOTE_DIRECT_PRODUCT,
    ROMINA_ORDERED_SOURCES,
    ROMINA_REMOTE_SPANISH_HR,
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
    assert [item.candidate.external_id for item in result.items] == ["sample-promising"]
    assert result.items[0].classification.verdict == RadarVerdict.promising
    assert [item.candidate.external_id for item in result.excluded_items] == ["sample-reject"]
    assert result.excluded_items[0].classification.verdict == RadarVerdict.reject


def test_profile_selection_includes_peter_and_romina_profiles() -> None:
    assert get_profile("peter-latam-remote-ai-fullstack-product") == (
        PETER_REMOTE_AI_FULLSTACK_PRODUCT
    )
    assert get_profile("romina-remote-spanish-hr") == ROMINA_REMOTE_SPANISH_HR
    assert PETER_US_REMOTE_DIRECT_PRODUCT == PETER_REMOTE_AI_FULLSTACK_PRODUCT


def test_title_filters_are_profile_scoped() -> None:
    assert not title_may_match_profile("Recruiter", PETER_REMOTE_AI_FULLSTACK_PRODUCT.target_roles)
    assert title_may_match_profile("AI Product Engineer", PETER_REMOTE_AI_FULLSTACK_PRODUCT.target_roles)
    assert title_may_match_profile("IT Recruiter", ROMINA_REMOTE_SPANISH_HR.target_roles)


def test_romina_profile_encodes_requested_source_order() -> None:
    enabled = [source for source in ROMINA_ORDERED_SOURCES if source.enabled]

    assert [source.id for source in enabled] == [
        "himalayas", "we_work_remotely", "remote_ok", "jobspresso", "randstad_ar",
        "linkedin", "computrabajo_ar", "bumeran", "getonboard", "hiringroom", "torre",
        "remote_latam", "jobgether",
    ]
    assert [source.order for source in ROMINA_ORDERED_SOURCES] == list(range(1, 26))
    assert all(source.min_qualified_to_stop == 3 for source in enabled)


def test_legacy_profile_sources_are_upgraded_without_touching_other_fields() -> None:
    profile_json = ROMINA_REMOTE_SPANISH_HR.model_dump(mode="json")
    for source in profile_json["ordered_sources"]:
        source.pop("acquisition_mode", None)
        source.pop("attribution_url", None)
    profile_json["candidate_summary"] = "Conservar este texto"

    upgraded = _upgrade_legacy_sources(profile_json)

    assert upgraded["candidate_summary"] == "Conservar este texto"
    assert [source["id"] for source in upgraded["ordered_sources"][:5]] == [
        "himalayas", "we_work_remotely", "remote_ok", "jobspresso", "randstad_ar",
    ]
    assert upgraded["ordered_sources"][0]["acquisition_mode"] == "himalayas_api"
    assert upgraded["ordered_sources"][3]["acquisition_mode"] == "jobspresso_wp_rest"


def test_himalayas_timestamp_accepts_epoch_seconds() -> None:
    assert _timestamp(1_800_000_000).startswith("2027-")


def test_ordered_discovery_continues_after_one_provider_fails() -> None:
    class FailingConnector(DiscoveryConnector):
        name = "failing"
        source_ids = frozenset({"himalayas"})

        def discover(self, profile, limit):
            return []

        def discover_source(self, profile, source, limit):
            raise RuntimeError("provider_unavailable: timeout")

    class WorkingConnector(DiscoveryConnector):
        name = "working"
        source_ids = frozenset({"remote_ok"})

        def discover(self, profile, limit):
            return [_valid_remote_raw(90)]

    profile = ROMINA_REMOTE_SPANISH_HR.model_copy(
        update={
            "ordered_sources": [
                SearchSource(
                    id="himalayas", label="Himalayas", domains=["himalayas.app"],
                    order=1, acquisition_mode=AcquisitionMode.himalayas_api,
                ),
                SearchSource(
                    id="remote_ok", label="Remote OK", domains=["remoteok.com"],
                    order=2, acquisition_mode=AcquisitionMode.remote_ok_api,
                ),
            ],
            "max_qualified_results": 1,
        }
    )

    result = run_discovery(
        profile=profile,
        connectors=[FailingConnector(), WorkingConnector()],
        limit=5,
        hydrate=False,
    )

    assert len(result.items) == 1
    assert result.source_summaries[0].status == "failed"
    assert result.source_summaries[0].error_code == "provider_unavailable"
    assert result.source_summaries[1].stop_reason == "target_reached"

def test_romina_remote_verified_spanish_hr_role_is_promising() -> None:
    classification = _classify_text(
        ROMINA_REMOTE_SPANISH_HR,
        title="HR Business Partner Senior",
        raw_text="""
        Buscamos HR Business Partner Senior para trabajo 100% remoto desde Argentina.
        Se requieren más de 5 años de experiencia en recursos humanos, selección de
        talento, relaciones laborales, legislación laboral y acompañamiento a líderes.
        La modalidad es completamente remota para nuestro equipo de LATAM.
        Postularme enviando el CV en español.
        """,
    )

    assert classification.verdict == RadarVerdict.promising
    assert classification.eligible is True
    assert classification.role_tier == 1
    assert all(
        check.status == EligibilityStatus.passed
        for check in classification.eligibility_checks
    )


def test_romina_remote_advanced_english_requirement_is_rejected() -> None:
    classification = _classify_text(
        ROMINA_REMOTE_SPANISH_HR,
        title="HR Business Partner Senior remoto",
        raw_text="""
        Buscamos HR Business Partner Senior para Argentina y LATAM. El trabajo es
        100% remoto. Requisito excluyente: inglés avanzado para reuniones diarias.
        Se requieren 5 años de experiencia en recursos humanos y relaciones laborales.
        Postularme enviando el CV en español.
        """,
    )

    assert classification.verdict == RadarVerdict.reject
    english_check = next(
        check
        for check in classification.eligibility_checks
        if check.criterion == "advanced_english"
    )
    assert english_check.status == EligibilityStatus.failed


def test_romina_remote_allows_non_exclusive_intermediate_english() -> None:
    classification = _classify_text(
        ROMINA_REMOTE_SPANISH_HR,
        title="People Partner Senior",
        raw_text="""
        Buscamos People Partner Senior para Argentina y América Latina. Posición
        100% remota con cinco años de experiencia en gestión de personas.
        Inglés intermedio deseable, no excluyente. Toda la descripción, entrevistas
        y postulación se realizan en español. Postularme ahora.
        """,
    )

    assert classification.eligible is True


def test_romina_remote_english_description_is_allowed_without_advanced_requirement() -> None:
    classification = _classify_text(
        ROMINA_REMOTE_SPANISH_HR,
        title="People Operations Senior",
        raw_text="""
        We are looking for a senior People Operations partner based in Argentina.
        This is a fully remote role for our Latin America team. You will lead human
        resources operations, employee relations, onboarding, and talent programs.
        Five years of experience are required. Apply now.
        """,
    )

    assert classification.verdict == RadarVerdict.promising
    assert classification.eligible is True
    assert not any(
        check.criterion in {"description_language", "application_language"}
        for check in classification.eligibility_checks
    )


def test_romina_remote_onsite_role_is_rejected_even_with_strong_hr_fit() -> None:
    classification = _classify_text(
        ROMINA_REMOTE_SPANISH_HR,
        title="HR Business Partner Senior",
        raw_text="""
        Buscamos HR Business Partner Senior para trabajo presencial en Buenos Aires,
        Argentina. Se requieren cinco años de experiencia en recursos humanos,
        reclutamiento, onboarding, clima y relaciones laborales. Postularme.
        """,
    )

    assert classification.verdict == RadarVerdict.reject
    assert any(
        check.criterion == "work_modality" and check.status == EligibilityStatus.failed
        for check in classification.eligibility_checks
    )


def test_romina_remote_spain_only_role_is_rejected() -> None:
    classification = _classify_text(
        ROMINA_REMOTE_SPANISH_HR,
        title="Talent Acquisition Specialist Senior",
        raw_text="""
        Buscamos especialista senior para una posición 100% remota. Es obligatorio
        residir en España y contar con permiso de trabajo en España. Gestionará
        selección, entrevistas y onboarding. Postularme en español.
        """,
    )

    assert classification.verdict == RadarVerdict.reject
    assert any(
        check.criterion == "hiring_geography"
        and check.status == EligibilityStatus.failed
        for check in classification.eligibility_checks
    )


def test_romina_remote_junior_role_is_rejected() -> None:
    classification = _classify_text(
        ROMINA_REMOTE_SPANISH_HR,
        title="Talent Acquisition Specialist Junior",
        raw_text="""
        Buscamos una persona junior sin experiencia para selección y reclutamiento.
        La posición es 100% remota desde Argentina para el equipo LATAM.
        Ofrecemos acompañamiento y aprendizaje. Postularme en español.
        """,
    )

    assert classification.verdict == RadarVerdict.reject
    assert any(
        check.criterion == "seniority" and check.status == EligibilityStatus.failed
        for check in classification.eligibility_checks
    )


def test_romina_closed_linkedin_phrase_is_rejected_before_fit() -> None:
    classification = _classify_text(
        ROMINA_REMOTE_SPANISH_HR,
        title="HR Business Partner Senior remoto",
        raw_text="""
        Buscamos HR Business Partner para Argentina y LATAM. Trabajo 100% remoto.
        Ya no se aceptan solicitudes. Cinco años de experiencia en recursos humanos.
        """,
    )

    assert classification.verdict == RadarVerdict.reject
    assert classification.page_type == PageType.expired
    assert classification.score == 0


def test_romina_irrelevant_results_are_rejected_before_fit_scoring() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "romina_irrelevant_results.json"
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
        ROMINA_REMOTE_SPANISH_HR, limit=1
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
        ROMINA_REMOTE_SPANISH_HR, limit=2
    )

    assert discoveries
    assert all(str(item.url) == "https://example.com/jobs/good" for item in discoveries)


def test_tavily_runs_tier_queries_for_one_ordered_source(monkeypatch) -> None:
    payloads: list[dict] = []

    def fake_post_json(_url, payload):
        payloads.append(payload)
        return {"results": []}

    monkeypatch.setattr("app.radar.connectors.tavily._post_json", fake_post_json)

    source = next(
        source for source in ROMINA_ORDERED_SOURCES if source.id == "linkedin"
    )
    TavilyConnector(api_key="test-key").discover_source(
        ROMINA_REMOTE_SPANISH_HR,
        source,
        limit=5,
    )

    assert len(payloads) == 3
    assert all(payload["include_domains"] == ["linkedin.com"] for payload in payloads)
    assert sum(payload["max_results"] for payload in payloads) == 5


def test_ordered_discovery_blacklist_overrides_an_enabled_source() -> None:
    connector = _OrderedFakeConnector(
        {
            "linkedin": [_valid_remote_raw(1)],
            "computrabajo_ar": [_valid_remote_raw(index + 10) for index in range(3)],
        }
    )
    profile = _ordered_test_profile(max_results=3).model_copy(
        update={"excluded_source_domains": ["linkedin.com"]}
    )

    result = run_discovery(
        profile=profile,
        connectors=[connector],
        limit=25,
        hydrate=False,
    )

    assert connector.calls == ["computrabajo_ar"]
    assert result.total_new == 3


def test_ordered_discovery_stops_after_three_new_qualified_results() -> None:
    connector = _OrderedFakeConnector(
        {
            "infojobs": [_valid_remote_raw(index) for index in range(3)],
            "linkedin": [_valid_remote_raw(index + 10) for index in range(3)],
        }
    )

    result = run_discovery(
        profile=_ordered_test_profile(max_results=3),
        connectors=[connector],
        limit=25,
        hydrate=False,
    )

    assert connector.calls == ["linkedin"]
    assert result.total_qualified == 3
    assert result.total_new == 3
    assert len(result.items) == 3
    assert not result.excluded_items
    assert result.source_summaries[0].continued_to_next is False
    assert result.source_summaries[0].stop_reason == "target_reached"


def test_ordered_discovery_continues_when_first_source_has_too_few() -> None:
    connector = _OrderedFakeConnector(
        {
            "linkedin": [_valid_remote_raw(1)],
            "computrabajo_ar": [_valid_remote_raw(index + 10) for index in range(3)],
        }
    )

    result = run_discovery(
        profile=_ordered_test_profile(max_results=3),
        connectors=[connector],
        limit=25,
        hydrate=False,
    )

    assert connector.calls == ["linkedin", "computrabajo_ar"]
    assert result.total_new == 4
    assert len(result.items) == 3
    assert result.source_summaries[0].continued_to_next is True
    assert result.source_summaries[0].stop_reason is None
    assert result.source_summaries[1].continued_to_next is False
    assert result.source_summaries[1].stop_reason == "target_reached"


def test_canonicalize_url_removes_tracking_params() -> None:
    url = "https://Jobs.Lever.co/acme/123/?utm_source=linkedin&foo=bar#apply"

    assert canonicalize_url(url) == "https://jobs.lever.co/acme/123?foo=bar"


def _ordered_test_profile(max_results: int):
    source_ids = {"linkedin", "computrabajo_ar"}
    return ROMINA_REMOTE_SPANISH_HR.model_copy(
        update={
            "ordered_sources": [
                source for source in ROMINA_ORDERED_SOURCES if source.id in source_ids
            ],
            "max_qualified_results": max_results,
        }
    )


class _OrderedFakeConnector(DiscoveryConnector):
    name = "ordered-fake"

    def __init__(self, batches: dict[str, list[RawDiscovery]]) -> None:
        self.batches = batches
        self.calls: list[str] = []

    def discover(self, profile, limit: int) -> list[RawDiscovery]:
        raise AssertionError("Ordered discovery should call discover_source")

    def discover_source(self, profile, source, limit: int) -> list[RawDiscovery]:
        self.calls.append(source.id)
        return self.batches.get(source.id, [])[:limit]


def _valid_remote_raw(index: int) -> RawDiscovery:
    return RawDiscovery(
        source=DiscoverySourceKind.tavily,
        title=f"HR Business Partner Senior {index}",
        company_name=f"Empresa {index}",
        url=f"https://example.com/jobs/hrbp-{index}",
        location_text="Argentina / LATAM",
        raw_text="""
        Buscamos HR Business Partner Senior para trabajar 100% remoto desde Argentina
        con equipos de América Latina. Se requieren cinco años de experiencia en
        recursos humanos, selección, relaciones laborales y acompañamiento a líderes.
        Toda la publicación está en español. Postularme ahora.
        """,
        metadata={
            "page_fetched": True,
            "page_http_status": 200,
            "application_text": "Postularme ahora",
        },
    )


def _classify_text(profile, title: str, raw_text: str):
    candidate = normalize_discovery(
        RawDiscovery(
            source=DiscoverySourceKind.sample,
            title=title,
            url="https://example.com/jobs/123",
            raw_text=raw_text,
            metadata={
                "page_fetched": True,
                "page_http_status": 200,
                "application_text": "Postularme",
            },
        )
    )
    return classify_candidate(candidate, profile)


def test_romina_rejects_country_only_restriction_even_when_latam_is_mentioned() -> None:
    classification = _classify_text(
        ROMINA_REMOTE_SPANISH_HR,
        title="Talent Acquisition Specialist Senior",
        raw_text="""
        Buscamos especialista senior para nuestro equipo de LATAM. La posición es
        100% remota, pero está disponible solo para residentes de Chile. Se requieren
        cinco años de experiencia en selección y recursos humanos. Postularme ahora.
        """,
    )

    assert classification.eligible is False
    assert any(
        check.criterion == "hiring_geography"
        and check.status == EligibilityStatus.failed
        for check in classification.eligibility_checks
    )


def test_romina_does_not_infer_the_role_from_description_body() -> None:
    classification = _classify_text(
        ROMINA_REMOTE_SPANISH_HR,
        title="Especialista Senior de Cultura",
        raw_text="""
        Buscamos especialista senior para trabajar 100% remoto desde Argentina.
        La persona colaborará con HR Business Partner y Talent Acquisition en
        iniciativas de recursos humanos para LATAM. Postularme en español.
        """,
    )

    assert classification.eligible is False
    assert any(
        check.criterion == "role" and check.status == EligibilityStatus.failed
        for check in classification.eligibility_checks
    )


def test_romina_rejects_expired_structured_valid_through_date() -> None:
    candidate = normalize_discovery(
        RawDiscovery(
            source=DiscoverySourceKind.tavily,
            title="HR Business Partner Senior",
            url="https://example.com/jobs/expired-structured",
            location_text="Argentina / LATAM",
            raw_text="""
            Buscamos HR Business Partner Senior para una posición 100% remota desde
            Argentina. Se requieren cinco años de experiencia en recursos humanos y
            relaciones laborales. La postulación se realiza en español. Postularme.
            """,
            metadata={
                "page_fetched": True,
                "page_http_status": 200,
                "application_text": "Postularme",
                "valid_through": "2020-01-01T00:00:00Z",
            },
        )
    )

    classification = classify_candidate(candidate, ROMINA_REMOTE_SPANISH_HR)

    assert classification.eligible is False
    assert any(
        check.criterion == "active_posting" and check.status == EligibilityStatus.failed
        for check in classification.eligibility_checks
    )


def test_ordered_discovery_limit_does_not_skip_later_sources() -> None:
    invalid_first_source = [
        RawDiscovery(
            source=DiscoverySourceKind.tavily,
            title=f"Asistente administrativo junior {index}",
            company_name=f"Empresa inválida {index}",
            url=f"https://example.com/jobs/invalid-{index}",
            raw_text="Puesto presencial junior de administración general.",
            metadata={"page_fetched": True, "page_http_status": 200},
        )
        for index in range(5)
    ]
    connector = _OrderedFakeConnector(
        {
            "linkedin": invalid_first_source,
            "computrabajo_ar": [_valid_remote_raw(index + 20) for index in range(3)],
        }
    )

    result = run_discovery(
        profile=_ordered_test_profile(max_results=3),
        connectors=[connector],
        limit=5,
        hydrate=False,
    )

    assert connector.calls == ["linkedin", "computrabajo_ar"]
    assert result.total_raw == 8
    assert len(result.items) == 3


def test_romina_allows_an_english_application_page_without_advanced_requirement() -> None:
    candidate = normalize_discovery(
        RawDiscovery(
            source=DiscoverySourceKind.tavily,
            title="People Partner Senior",
            url="https://example.com/jobs/spanish-job-english-form",
            location_text="Argentina / LATAM",
            raw_text="""
            Buscamos People Partner Senior para una posición 100% remota desde
            Argentina. Se requieren cinco años de experiencia en recursos humanos,
            selección y relaciones laborales. La descripción está en español.
            Postularme ahora.
            """,
            metadata={
                "page_fetched": True,
                "page_http_status": 200,
                "application_text": (
                    "Apply now. Complete the job application with your experience, "
                    "skills, contact details, resume, and professional background."
                ),
            },
        )
    )

    classification = classify_candidate(candidate, ROMINA_REMOTE_SPANISH_HR)

    assert classification.eligible is True
    assert not any(
        check.criterion == "application_language"
        for check in classification.eligibility_checks
    )


def test_romina_accepts_mendoza_hybrid_and_rejects_hybrid_elsewhere() -> None:
    mendoza = _classify_text(
        ROMINA_REMOTE_SPANISH_HR,
        title="HR Business Partner Senior",
        raw_text="""
        Posición híbrida en Mendoza, Argentina. Buscamos HRBP con cinco años de
        experiencia en recursos humanos y selección. Postularme ahora.
        """,
    )
    cordoba = _classify_text(
        ROMINA_REMOTE_SPANISH_HR,
        title="HR Business Partner Senior",
        raw_text="""
        Posición híbrida en Córdoba, Argentina. Buscamos HRBP con cinco años de
        experiencia en recursos humanos y selección. Postularme ahora.
        """,
    )

    assert mendoza.eligible is True
    assert cordoba.eligible is False
    assert any(
        check.criterion == "work_modality" and check.status == EligibilityStatus.failed
        for check in cordoba.eligibility_checks
    )


def test_romina_rejects_only_an_explicit_salary_below_floor() -> None:
    below = _classify_text(
        ROMINA_REMOTE_SPANISH_HR,
        title="IT Recruiter Senior",
        raw_text="""
        Trabajo 100% remoto desde Argentina y LATAM. Se requieren cinco años de
        experiencia. Salario USD 800 mensual. Postularme ahora.
        """,
    )
    undisclosed = _classify_text(
        ROMINA_REMOTE_SPANISH_HR,
        title="IT Recruiter Senior",
        raw_text="""
        Trabajo 100% remoto desde Argentina y LATAM. Se requieren cinco años de
        experiencia en selección de talento tecnológico. Postularme ahora.
        """,
    )

    assert below.eligible is False
    assert below.facts.salary_min_usd_monthly == 800
    assert undisclosed.eligible is True
    assert undisclosed.facts.salary_min_usd_monthly is None


def test_romina_role_matching_accepts_common_title_variants() -> None:
    analyst = _classify_text(
        ROMINA_REMOTE_SPANISH_HR,
        title="Analista Senior de RRHH",
        raw_text="""
        Buscamos una persona para trabajo 100% remoto desde Argentina y LATAM.
        Se requieren cinco años de experiencia en recursos humanos, selección y
        relaciones laborales. La postulación se realiza en español. Postularme.
        """,
    )
    recruiter = _classify_text(
        ROMINA_REMOTE_SPANISH_HR,
        title="Recruiter IT Senior",
        raw_text="""
        Buscamos Recruiter IT Senior para una posición 100% remota desde Argentina.
        Se requieren cinco años de experiencia en selección de perfiles tecnológicos
        y acompañamiento a líderes de LATAM. Postularme en español.
        """,
    )

    assert analyst.eligible is True
    assert analyst.role_tier == 1
    assert recruiter.eligible is True
    assert recruiter.role_tier == 2


def test_romina_rejects_a_closed_application_page() -> None:
    candidate = normalize_discovery(
        RawDiscovery(
            source=DiscoverySourceKind.tavily,
            title="HR Business Partner Senior",
            url="https://example.com/jobs/closed-application",
            location_text="Argentina / LATAM",
            raw_text="""
            Buscamos HR Business Partner Senior para una posición 100% remota desde
            Argentina. Se requieren cinco años de experiencia en recursos humanos y
            relaciones laborales. La descripción está en español. Postularme ahora.
            """,
            metadata={
                "page_fetched": True,
                "page_http_status": 200,
                "application_text": (
                    "Postulación cerrada. Ya no se aceptan solicitudes para esta vacante."
                ),
            },
        )
    )

    classification = classify_candidate(candidate, ROMINA_REMOTE_SPANISH_HR)

    assert classification.eligible is False
    assert any(
        check.criterion == "active_posting" and check.status == EligibilityStatus.failed
        for check in classification.eligibility_checks
    )
