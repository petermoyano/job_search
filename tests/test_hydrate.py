from app.radar import hydrate as hydrate_module
from app.radar.models import DiscoverySourceKind, RawDiscovery


def test_hydration_prefers_verified_job_posting_data(monkeypatch) -> None:
    html = """
    <html lang="es">
      <body>
        <h1>People Partner Senior</h1>
        <p>
          Buscamos una persona con cinco años de experiencia para una posición
          100% remota desde Argentina. La descripción y el proceso están en español.
        </p>
        <a href="/postular">Postularme ahora</a>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "JobPosting",
          "title": "People Partner Senior",
          "description": "<p>Responsabilidades de recursos humanos y relaciones laborales.</p>",
          "datePosted": "2026-07-29T12:00:00Z",
          "validThrough": "2026-08-29T12:00:00Z",
          "jobLocationType": "TELECOMMUTE",
          "hiringOrganization": {"@type": "Organization", "name": "Empresa Verificada"},
          "applicantLocationRequirements": {"@type": "Country", "name": "Argentina"}
        }
        </script>
      </body>
    </html>
    """
    page = hydrate_module._FetchedPage(
        status=200,
        content_type="text/html",
        text=html,
        final_url="https://example.com/jobs/people-partner",
    )
    monkeypatch.setattr(hydrate_module, "_fetch_page", lambda _url: page)
    monkeypatch.setattr(
        hydrate_module,
        "_fetch_application_text",
        lambda _application_url, _job_url: "Postularme en español",
    )
    discovery = RawDiscovery(
        source=DiscoverySourceKind.tavily,
        title="Resultado de búsqueda | empleo",
        company_name="Dato incompleto",
        url="https://example.com/jobs/people-partner",
        raw_text="English search-engine snippet that should not classify the description.",
    )

    hydrated = hydrate_module.hydrate_discovery(discovery)

    assert hydrated.title == "People Partner Senior"
    assert hydrated.company_name == "Empresa Verificada"
    assert hydrated.location_text == "Argentina"
    assert hydrated.metadata["published_date"] == "2026-07-29T12:00:00Z"
    assert hydrated.metadata["valid_through"] == "2026-08-29T12:00:00Z"
    assert hydrated.metadata["application_url"] == "https://example.com/postular"
    assert hydrated.metadata["application_fetched"] is True
    assert hydrated.metadata["application_text"] == "Postularme en español"
    assert hydrated.metadata["discovery_snippet"].startswith("English search-engine")
    assert "English search-engine" not in hydrated.raw_text


def test_hydration_rejects_private_or_unsupported_urls() -> None:
    discovery = RawDiscovery(
        source=DiscoverySourceKind.tavily,
        title="Internal job",
        url="http://127.0.0.1/jobs/secret",
        raw_text="contenido",
    )

    hydrated = hydrate_module.hydrate_discovery(discovery)

    assert hydrated.metadata["page_fetched"] is False
    assert hydrated.metadata["page_fetch_error"] == "unsafe_or_unsupported_url"
