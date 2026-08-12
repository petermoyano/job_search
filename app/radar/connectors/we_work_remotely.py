from __future__ import annotations

from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET

from app.radar.connectors.base import DiscoveryConnector
from app.radar.connectors.common import get_bytes, html_to_text, title_may_match_profile
from app.radar.models import (
    DiscoverySourceKind,
    RawDiscovery,
    SearchProfile,
    SearchSource,
)


WE_WORK_REMOTELY_RSS_URL = "https://weworkremotely.com/remote-jobs.rss"


class WeWorkRemotelyConnector(DiscoveryConnector):
    name = "we_work_remotely"
    source_ids = frozenset({"we_work_remotely"})

    def discover(self, profile: SearchProfile, limit: int) -> list[RawDiscovery]:
        source = SearchSource(
            id="we_work_remotely",
            label="We Work Remotely",
            domains=["weworkremotely.com"],
            order=1,
        )
        return self.discover_source(profile, source, limit)

    def discover_source(
        self, profile: SearchProfile, source: SearchSource, limit: int
    ) -> list[RawDiscovery]:
        try:
            root = ET.fromstring(get_bytes(WE_WORK_REMOTELY_RSS_URL))
        except ET.ParseError as exc:
            raise RuntimeError("provider_invalid_xml") from exc
        discoveries: list[RawDiscovery] = []
        for node in root.iter():
            if _local_name(node.tag) not in {"item", "entry"}:
                continue
            item = _map_item(node, profile, source)
            if item is None:
                continue
            discoveries.append(item)
            if len(discoveries) >= limit:
                break
        return discoveries


def _map_item(
    node: ET.Element, profile: SearchProfile, source: SearchSource
) -> RawDiscovery | None:
    raw_title = _child_text(node, "title")
    link = _child_text(node, "link") or _link_href(node)
    if not raw_title or not link:
        return None
    company, title = _split_title(raw_title)
    if not title_may_match_profile(title, profile.target_roles):
        return None
    description = (
        _child_text(node, "description")
        or _child_text(node, "content")
        or _child_text(node, "summary")
        or ""
    )
    region = _child_text(node, "region")
    worldwide = bool(
        region and region.casefold() in {"anywhere in the world", "worldwide", "anywhere"}
    )
    published = (
        _child_text(node, "pubDate")
        or _child_text(node, "published")
        or _child_text(node, "updated")
    )
    return RawDiscovery(
        source=DiscoverySourceKind.we_work_remotely,
        title=title,
        company_name=company,
        url=link,
        location_text=region or "Remote",
        raw_text=html_to_text(description),
        external_id=_child_text(node, "guid") or link,
        metadata={
            "source_id": source.id,
            "source_label": source.label,
            "acquisition_mode": "we_work_remotely_rss",
            "attribution_url": link,
            "application_url": link,
            "published_date": _normalize_date(published),
            "provider_status": "active",
            "provider_remote_claim_trusted": True,
            "valid_through": _normalize_date(_child_text(node, "expires_at")),
            "provider_worldwide": worldwide,
            "applicant_locations": [] if worldwide else ([region] if region else []),
        },
    )


def _child_text(node: ET.Element, name: str) -> str | None:
    for child in node:
        if _local_name(child.tag) == name and child.text and child.text.strip():
            return child.text.strip()
    return None


def _link_href(node: ET.Element) -> str | None:
    for child in node:
        if _local_name(child.tag) == "link" and child.attrib.get("href"):
            return child.attrib["href"].strip()
    return None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _split_title(value: str) -> tuple[str | None, str]:
    if ":" not in value:
        return None, value.strip()
    company, title = value.split(":", 1)
    return company.strip() or None, title.strip()


def _normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).isoformat()
    except (TypeError, ValueError):
        return value

