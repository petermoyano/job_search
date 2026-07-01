from app.radar.connectors.sample import SampleConnector
from app.radar.discovery import run_discovery
from app.radar.models import RadarVerdict
from app.radar.normalize import canonicalize_url
from app.radar.profiles import PETER_US_REMOTE_DIRECT_PRODUCT


def test_sample_discovery_classifies_promising_and_reject() -> None:
    result = run_discovery(
        profile=PETER_US_REMOTE_DIRECT_PRODUCT,
        connectors=[SampleConnector()],
        limit=10,
    )

    assert result.total_raw == 2
    assert result.total_unique == 2
    verdicts = {item.candidate.external_id: item.classification.verdict for item in result.items}
    assert verdicts["sample-promising"] == RadarVerdict.promising
    assert verdicts["sample-reject"] == RadarVerdict.reject


def test_canonicalize_url_removes_tracking_params() -> None:
    url = "https://Jobs.Lever.co/acme/123/?utm_source=linkedin&foo=bar#apply"

    assert canonicalize_url(url) == "https://jobs.lever.co/acme/123?foo=bar"

