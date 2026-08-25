from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import TypeVar
from uuid import UUID

from sqlalchemy.orm import Session

from app.documents.auth import AuthContext
from app.documents.models import Document, DocumentStatus, now_utc
from app.documents.repository import DocumentRepository
from app.documents.resume_schemas import (
    ResumeCertificationV1,
    ResumeEducationV1,
    ResumeExperienceV1,
    ResumeLanguageV1,
    ResumeProfileDraftV1,
    ResumeSkillV1,
)
from app.documents.schemas import ApplyResumeDraftRequest, ResumeApplySection
from app.radar.models import SearchProfileDocument
from app.radar.profile_store import (
    ProfileRevisionConflictError,
    get_profile_document,
    update_professional_profile_document,
)


class ResumeDraftNotFoundError(Exception):
    pass


class ResumeDraftProfileMismatchError(Exception):
    pass


class ResumeDraftNotApplicableError(Exception):
    pass


class ResumeProfileNotFoundError(Exception):
    pass


class ResumeApplyAccessDeniedError(Exception):
    pass


@dataclass(frozen=True)
class AppliedResumeDraft:
    profile_document: SearchProfileDocument
    draft_id: UUID
    applied_at: datetime


class ResumeDraftService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = DocumentRepository(session)

    def list_profile_documents(
        self,
        *,
        profile_id: str,
        auth_context: AuthContext,
    ) -> list[Document]:
        self._authorize_job_search(auth_context)
        try:
            get_profile_document(self.session, profile_id)
        except ValueError as exc:
            raise ResumeProfileNotFoundError("Profile not found") from exc
        return self.repository.list_recent_profile_documents(
            profile_id=profile_id,
            auth_context=auth_context,
        )

    def apply(
        self,
        *,
        draft_id: UUID,
        payload: ApplyResumeDraftRequest,
        auth_context: AuthContext,
    ) -> AppliedResumeDraft:
        self._authorize_job_search(auth_context)
        draft = self.repository.get_draft_by_id_scoped(
            draft_id=draft_id,
            auth_context=auth_context,
            for_update=True,
        )
        if draft is None:
            raise ResumeDraftNotFoundError("Resume draft not found")

        document = draft.document
        context_profile_id = (
            document.context.get("profile_id")
            if isinstance(document.context, dict)
            else None
        )
        if (
            draft.profile_id != payload.profile_id
            or context_profile_id != payload.profile_id
        ):
            raise ResumeDraftProfileMismatchError(
                "Resume draft does not belong to this profile"
            )
        if document.status != DocumentStatus.COMPLETED:
            raise ResumeDraftNotApplicableError(
                "Only a completed resume draft can be applied"
            )

        try:
            current = get_profile_document(self.session, payload.profile_id)
        except ValueError as exc:
            raise ResumeProfileNotFoundError("Profile not found") from exc
        if (
            payload.expected_revision is not None
            and payload.expected_revision != current.revision
        ):
            raise ProfileRevisionConflictError(
                "The profile changed. Reload it before applying the resume."
            )

        detected = ResumeProfileDraftV1.model_validate(draft.payload)
        professional, candidate_summary = apply_selected_sections(
            current=current.profile.professional_profile,
            detected=detected,
            sections=set(payload.sections),
            current_candidate_summary=current.profile.candidate_summary,
        )
        updated = update_professional_profile_document(
            self.session,
            payload.profile_id,
            professional_profile=professional,
            candidate_summary=candidate_summary,
            expected_revision=current.revision,
        )
        applied_at = now_utc()
        draft.applied_at = applied_at
        self.session.commit()
        return AppliedResumeDraft(
            profile_document=updated,
            draft_id=draft.id,
            applied_at=applied_at,
        )

    @staticmethod
    def _authorize_job_search(auth_context: AuthContext) -> None:
        if not auth_context.allows(
            source_app="job-search",
            tenant_id="job-search",
        ):
            raise ResumeApplyAccessDeniedError(
                "Credential is not authorized for resume profile operations"
            )


def _text(value: str | None, fallback: str | None) -> str | None:
    return value.strip() if value is not None and value.strip() else fallback


def _key(*values: str | None) -> tuple[str, ...]:
    return tuple((value or "").strip().casefold() for value in values)


T = TypeVar("T")


def _dedupe(items: Iterable[T], key: Callable[[T], object]) -> list[T]:
    result: list[T] = []
    seen: set[object] = set()
    for item in items:
        identity = key(item)
        if identity in seen:
            continue
        seen.add(identity)
        result.append(item)
    return result


def _merge_skills(
    current: list[ResumeSkillV1], detected: list[ResumeSkillV1]
) -> list[ResumeSkillV1]:
    return _dedupe(
        [*current, *detected],
        lambda item: item.name.strip().casefold(),
    )


def _merge_languages(
    current: list[ResumeLanguageV1], detected: list[ResumeLanguageV1]
) -> list[ResumeLanguageV1]:
    detected_by_key = {
        item.language.strip().casefold(): item for item in detected
    }
    merged = [
        detected_by_key.pop(item.language.strip().casefold(), item)
        for item in current
    ]
    merged.extend(detected_by_key.values())
    return merged


def _dedupe_experience(
    items: list[ResumeExperienceV1],
) -> list[ResumeExperienceV1]:
    return _dedupe(
        items,
        lambda item: _key(
            item.company,
            item.title,
            item.start_date,
            item.end_date,
        ),
    )


def _dedupe_education(
    items: list[ResumeEducationV1],
) -> list[ResumeEducationV1]:
    return _dedupe(
        items,
        lambda item: _key(
            item.institution,
            item.degree,
            item.field_of_study,
            item.start_date,
            item.end_date,
        ),
    )


def _merge_certifications(
    current: list[ResumeCertificationV1],
    detected: list[ResumeCertificationV1],
) -> list[ResumeCertificationV1]:
    return _dedupe(
        [*current, *detected],
        lambda item: _key(item.name, item.issuer),
    )


def apply_selected_sections(
    *,
    current: ResumeProfileDraftV1,
    detected: ResumeProfileDraftV1,
    sections: set[ResumeApplySection],
    current_candidate_summary: str | None,
) -> tuple[ResumeProfileDraftV1, str | None]:
    update: dict[str, object] = {}
    scalar_sections = {
        ResumeApplySection.full_name: "full_name",
        ResumeApplySection.headline: "headline",
        ResumeApplySection.professional_summary: "professional_summary",
        ResumeApplySection.location: "location",
    }
    for section, field_name in scalar_sections.items():
        if section in sections:
            update[field_name] = _text(
                getattr(detected, field_name),
                getattr(current, field_name),
            )
    if ResumeApplySection.skills in sections:
        update["skills"] = _merge_skills(current.skills, detected.skills)
    if ResumeApplySection.experience in sections:
        update["experience"] = _dedupe_experience(detected.experience)
    if ResumeApplySection.education in sections:
        update["education"] = _dedupe_education(detected.education)
    if ResumeApplySection.languages in sections:
        update["languages"] = _merge_languages(current.languages, detected.languages)
    if ResumeApplySection.certifications in sections:
        update["certifications"] = _merge_certifications(
            current.certifications,
            detected.certifications,
        )

    candidate_summary = None
    if ResumeApplySection.professional_summary in sections:
        candidate_summary = _text(
            detected.professional_summary,
            current_candidate_summary,
        )
    return current.model_copy(update=update), candidate_summary
