from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.documents.auth import AuthContext, get_auth_context
from app.documents.repository import DocumentRepository
from app.documents.schemas import DocumentRead, UploadUrlRequest, UploadUrlResponse
from app.documents.service import (
    DocumentAccessDeniedError,
    DocumentNotFoundError,
    DocumentService,
    FileTooLargeError,
    InvalidUploadStateError,
    UploadObjectNotFoundError,
    UploadValidationError,
)
from app.documents.storage import (
    DocumentStorage,
    StorageUnavailableError,
    get_document_storage,
)


router = APIRouter(prefix="/documents", tags=["documents"])


def get_document_service(
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[DocumentStorage, Depends(get_document_storage)],
) -> DocumentService:
    return DocumentService(
        repository=DocumentRepository(db),
        storage=storage,
        settings=get_settings(),
    )


@router.post(
    "/upload-url",
    response_model=UploadUrlResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_upload_url(
    payload: UploadUrlRequest,
    auth_context: Annotated[AuthContext, Depends(get_auth_context)],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> UploadUrlResponse:
    try:
        result = service.create_upload(payload=payload, auth_context=auth_context)
    except DocumentAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except FileTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except StorageUnavailableError as exc:
        raise HTTPException(
            status_code=502, detail="Document storage unavailable"
        ) from exc
    return UploadUrlResponse(
        document_id=result.document.id,
        status=result.document.status,
        upload_url=result.upload.url,
        expires_in=result.expires_in,
        required_headers=result.upload.required_headers,
    )


@router.post(
    "/{document_id}/complete-upload",
    response_model=DocumentRead,
)
def complete_upload(
    document_id: UUID,
    auth_context: Annotated[AuthContext, Depends(get_auth_context)],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentRead:
    try:
        return DocumentRead.model_validate(
            service.complete_upload(document_id=document_id, auth_context=auth_context)
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (
        InvalidUploadStateError,
        UploadObjectNotFoundError,
        UploadValidationError,
    ) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except StorageUnavailableError as exc:
        raise HTTPException(
            status_code=502, detail="Document storage unavailable"
        ) from exc


@router.get("/{document_id}", response_model=DocumentRead)
def read_document(
    document_id: UUID,
    auth_context: Annotated[AuthContext, Depends(get_auth_context)],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentRead:
    try:
        return DocumentRead.model_validate(
            service.get_document(document_id=document_id, auth_context=auth_context)
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
