from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.documents.auth import AuthContext, get_auth_context
from app.documents.repository import DocumentRepository
from app.knowledge.contracts import (
    KnowledgeGenerateRequest,
    KnowledgeGenerateResponse,
    KnowledgeRetrieveRequest,
    KnowledgeRetrieveResponse,
)
from app.knowledge.generation import (
    KnowledgeGenerationAccessDeniedError,
    KnowledgeGenerationConfigurationError,
    KnowledgeGenerationRejectedError,
    KnowledgeGenerationService,
    KnowledgeGenerationUnavailableError,
)
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


def get_knowledge_generation_service() -> KnowledgeGenerationService:
    return KnowledgeGenerationService(settings=get_settings())


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


@router.post("/generate", response_model=KnowledgeGenerateResponse)
def generate_knowledge_answer(
    payload: KnowledgeGenerateRequest,
    auth_context: Annotated[AuthContext, Depends(get_auth_context)],
    service: Annotated[
        KnowledgeGenerationService, Depends(get_knowledge_generation_service)
    ],
) -> KnowledgeGenerateResponse:
    try:
        return service.generate(payload=payload, auth_context=auth_context)
    except KnowledgeGenerationAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except (
        KnowledgeGenerationConfigurationError,
        KnowledgeGenerationUnavailableError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Knowledge generation is temporarily unavailable",
        ) from exc
    except KnowledgeGenerationRejectedError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Knowledge generation request was rejected",
        ) from exc
