from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.documents.resume_schemas import ResumeProfileDraftV1
from app.models import RadarProfileConfig
from app.radar.models import (
    SearchProfile,
    SearchProfileDocument,
    SearchProfileUpdateRequest,
)
from app.radar.profiles import (
    PROFILES,
    build_role_tier_queries,
    get_profile as get_static_profile,
)


class ProfileRevisionConflictError(ValueError):
    pass


def get_effective_profile(db: Session, profile_id: str) -> SearchProfile:
    fallback = get_static_profile(profile_id)
    stored = db.get(RadarProfileConfig, profile_id)
    if stored is None:
        return fallback
    return SearchProfile.model_validate(_upgrade_legacy_sources(stored.profile_json))


def list_effective_profiles(db: Session) -> list[SearchProfile]:
    stored = {
        item.profile_id: item for item in db.scalars(select(RadarProfileConfig)).all()
    }
    return [
        SearchProfile.model_validate(
            _upgrade_legacy_sources(stored[profile_id].profile_json)
        )
        if profile_id in stored
        else profile
        for profile_id, profile in PROFILES.items()
    ]


def get_profile_document(db: Session, profile_id: str) -> SearchProfileDocument:
    fallback = get_static_profile(profile_id)
    stored = db.get(RadarProfileConfig, profile_id)
    if stored is None:
        return SearchProfileDocument(profile=fallback, revision=0, persisted=False)
    return SearchProfileDocument(
        profile=SearchProfile.model_validate(
            _upgrade_legacy_sources(stored.profile_json)
        ),
        revision=stored.revision,
        persisted=True,
    )


def update_profile_document(
    db: Session,
    profile_id: str,
    payload: SearchProfileUpdateRequest,
) -> SearchProfileDocument:
    fallback = get_static_profile(profile_id)
    stored = db.scalar(
        select(RadarProfileConfig)
        .where(RadarProfileConfig.profile_id == profile_id)
        .with_for_update()
    )
    current_revision = stored.revision if stored is not None else 0
    if payload.expected_revision != current_revision:
        raise ProfileRevisionConflictError(
            "El perfil cambió desde que se abrió. Recargalo antes de volver a guardar."
        )
    if payload.profile.id != profile_id:
        raise ValueError("El id del perfil no coincide con la URL.")

    next_revision = current_revision + 1
    normalized = _normalize_profile(
        payload.profile,
        fallback=fallback,
        revision=next_revision,
    )
    if stored is None:
        stored = RadarProfileConfig(
            profile_id=profile_id,
            revision=next_revision,
            profile_json=normalized.model_dump(mode="json"),
        )
        db.add(stored)
    else:
        stored.revision = next_revision
        stored.profile_json = normalized.model_dump(mode="json")
    db.flush()
    return SearchProfileDocument(
        profile=normalized,
        revision=next_revision,
        persisted=True,
    )


def update_professional_profile_document(
    db: Session,
    profile_id: str,
    *,
    professional_profile: ResumeProfileDraftV1,
    candidate_summary: str | None,
    expected_revision: int,
) -> SearchProfileDocument:
    """Persist resume-derived data without replacing Radar settings."""
    fallback = get_static_profile(profile_id)
    stored = db.scalar(
        select(RadarProfileConfig)
        .where(RadarProfileConfig.profile_id == profile_id)
        .with_for_update()
    )
    current_revision = stored.revision if stored is not None else 0
    if expected_revision != current_revision:
        raise ProfileRevisionConflictError(
            "The profile changed. Reload it before applying the resume."
        )
    current = (
        SearchProfile.model_validate(_upgrade_legacy_sources(stored.profile_json))
        if stored is not None
        else fallback
    )
    next_revision = current_revision + 1
    updates: dict[str, object] = {
        "professional_profile": professional_profile,
        "version": f"config-r{next_revision}",
    }
    if candidate_summary is not None:
        updates["candidate_summary"] = candidate_summary
    updated = current.model_copy(update=updates)
    if stored is None:
        stored = RadarProfileConfig(
            profile_id=profile_id,
            revision=next_revision,
            profile_json=updated.model_dump(mode="json"),
        )
        db.add(stored)
    else:
        stored.revision = next_revision
        stored.profile_json = updated.model_dump(mode="json")
    db.flush()
    return SearchProfileDocument(
        profile=updated,
        revision=next_revision,
        persisted=True,
    )


def _normalize_profile(
    profile: SearchProfile,
    *,
    fallback: SearchProfile,
    revision: int,
) -> SearchProfile:
    ordered_sources = [
        source.model_copy(update={"order": index})
        for index, source in enumerate(
            sorted(profile.ordered_sources, key=lambda item: item.order), start=1
        )
    ]
    if not any(source.enabled for source in ordered_sources):
        raise ValueError("Debe quedar al menos una fuente habilitada.")
    target_roles = [
        title
        for tier in sorted(profile.role_tiers, key=lambda item: item.tier)
        for title in tier.titles
        if title.strip()
    ]
    if not target_roles:
        target_roles = profile.target_roles
    if not target_roles:
        raise ValueError("Debe quedar al menos un puesto objetivo.")
    excluded_domains = list(
        dict.fromkeys(
            domain.strip().casefold().removeprefix("www.")
            for domain in profile.excluded_source_domains
            if domain.strip()
        )
    )
    preferred_domains = list(
        dict.fromkeys(
            domain.strip().casefold().removeprefix("www.")
            for source in ordered_sources
            if source.enabled
            for domain in source.domains
            if domain.strip()
            and domain.strip().casefold().removeprefix("www.") not in excluded_domains
        )
    )
    queries = (
        build_role_tier_queries(
            profile.role_tiers, query_suffix=" OR ".join(profile.required_terms)
        )
        if profile.role_tiers
        else profile.queries
    )
    return profile.model_copy(
        update={
            "id": fallback.id,
            "version": f"config-r{revision}",
            "owner_id": fallback.owner_id,
            "owner_name": fallback.owner_name,
            "target_roles": target_roles,
            "ordered_sources": ordered_sources,
            "preferred_source_domains": preferred_domains,
            "excluded_source_domains": excluded_domains,
            "queries": queries,
        }
    )


def _upgrade_legacy_sources(profile_json: dict) -> dict:
    """Apply newly supported acquisition modes without overriding later user choices."""
    raw_sources = profile_json.get("ordered_sources")
    if not isinstance(raw_sources, list):
        return profile_json

    structured = {
        "himalayas": ("himalayas_api", "https://himalayas.app", 10),
        "we_work_remotely": ("we_work_remotely_rss", "https://weworkremotely.com", 10),
        "remote_ok": ("remote_ok_api", "https://remoteok.com", 15),
        "jobspresso": ("jobspresso_wp_rest", "https://jobspresso.co", 10),
        "randstad_ar": ("randstad_html", "https://www.randstad.com.ar", 10),
    }
    sources: list[dict] = []
    for source in raw_sources:
        if not isinstance(source, dict):
            continue
        upgraded = {**source}
        capability = structured.get(str(upgraded.get("id")))
        current_mode = upgraded.get("acquisition_mode")
        if capability and current_mode in {None, "web_search"}:
            upgraded["acquisition_mode"] = capability[0]
            upgraded["attribution_url"] = capability[1]
            upgraded["enabled"] = True
            upgraded["max_results"] = capability[2]
        elif current_mode is None:
            upgraded["acquisition_mode"] = "web_search"
        sources.append(upgraded)

    priority = {
        "himalayas": 0,
        "we_work_remotely": 1,
        "remote_ok": 2,
        "jobspresso": 3,
        "randstad_ar": 4,
    }
    sources.sort(
        key=lambda source: (
            priority.get(str(source.get("id")), 5),
            int(source.get("order") or 999),
        )
    )
    for index, source in enumerate(sources, start=1):
        source["order"] = index
    return {**profile_json, "ordered_sources": sources}
