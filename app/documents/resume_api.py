from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.documents.auth import AuthContext, get_auth_context
from app.documents.resume_apply import (
    ResumeApplyAccessDeniedError,
    ResumeDraftNotApplicableError,
    ResumeDraftNotFoundError,
    ResumeDraftProfileMismatchError,
    ResumeDraftService,
    ResumeProfileNotFoundError,
)
from app.documents.schemas import (
    ApplyResumeDraftRequest,
    ApplyResumeDraftResponse,
    DocumentRead,
)
from app.radar.profile_store import ProfileRevisionConflictError


router = APIRouter(tags=["resume profiles"])


def get_resume_draft_service(
    db: Annotated[Session, Depends(get_db)],
) -> ResumeDraftService:
    return ResumeDraftService(db)


@router.get(
    "/profiles/{profile_id}/resume-documents",
    response_model=list[DocumentRead],
)
def list_profile_resume_documents(
    profile_id: str,
    auth_context: Annotated[AuthContext, Depends(get_auth_context)],
    service: Annotated[ResumeDraftService, Depends(get_resume_draft_service)],
) -> list[DocumentRead]:
    try:
        documents = service.list_profile_documents(
            profile_id=profile_id,
            auth_context=auth_context,
        )
        return [DocumentRead.model_validate(document) for document in documents]
    except ResumeApplyAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ResumeProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/resume-profile-drafts/{draft_id}/apply",
    response_model=ApplyResumeDraftResponse,
)
def apply_resume_profile_draft(
    draft_id: UUID,
    payload: ApplyResumeDraftRequest,
    auth_context: Annotated[AuthContext, Depends(get_auth_context)],
    service: Annotated[ResumeDraftService, Depends(get_resume_draft_service)],
) -> ApplyResumeDraftResponse:
    try:
        result = service.apply(
            draft_id=draft_id,
            payload=payload,
            auth_context=auth_context,
        )
        return ApplyResumeDraftResponse(
            **result.profile_document.model_dump(),
            applied_draft_id=result.draft_id,
            applied_at=result.applied_at,
        )
    except ResumeApplyAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (ResumeDraftNotFoundError, ResumeProfileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (
        ResumeDraftProfileMismatchError,
        ResumeDraftNotApplicableError,
        ProfileRevisionConflictError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
