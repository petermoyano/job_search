from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.documents.auth import AuthContext, get_auth_context
from app.documents.repository import DocumentRepository
from app.knowledge.contracts import KnowledgeRetrieveRequest, KnowledgeRetrieveResponse
from app.knowledge.retrieval import (
    KnowledgeRetrievalAccessDeniedError,
    KnowledgeRetrievalConfigurationError,
    KnowledgeRetrievalService,
    KnowledgeRetrievalUnavailableError,
)


router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def get_knowledge_retrieval_service(
    db: Annotated[Session, Depends(get_db)],
) -> KnowledgeRetrievalService:
    return KnowledgeRetrievalService(
        repository=DocumentRepository(db),
        settings=get_settings(),
    )


@router.post("/retrieve", response_model=KnowledgeRetrieveResponse)
def retrieve_knowledge(
    payload: KnowledgeRetrieveRequest,
    auth_context: Annotated[AuthContext, Depends(get_auth_context)],
    service: Annotated[
        KnowledgeRetrievalService, Depends(get_knowledge_retrieval_service)
    ],
) -> KnowledgeRetrieveResponse:
    try:
        return service.retrieve(payload=payload, auth_context=auth_context)
    except KnowledgeRetrievalAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except (
        KnowledgeRetrievalConfigurationError,
        KnowledgeRetrievalUnavailableError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Knowledge retrieval is temporarily unavailable",
        ) from exc
