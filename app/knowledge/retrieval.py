from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Protocol
from uuid import UUID

import boto3  # type: ignore[import-untyped]
from botocore.config import Config
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ConnectionClosedError,
    EndpointConnectionError,
    ReadTimeoutError,
)

from app.core.config import Settings
from app.documents.auth import AuthContext
from app.documents.repository import DocumentRepository
from app.knowledge.contracts import (
    CRANE_INTELLIGENCE_SOURCE_APP,
    KnowledgeCitation,
    KnowledgeRetrieveRequest,
    KnowledgeRetrieveResponse,
)


TRANSIENT_ERROR_CODES = {
    "InternalServerException",
    "ServiceQuotaExceededException",
    "ServiceUnavailableException",
    "ThrottlingException",
    "TooManyRequestsException",
}
MAX_EXCERPT_CHARACTERS = 2_000
MAX_TITLE_CHARACTERS = 255


class KnowledgeRetrievalAccessDeniedError(Exception):
    pass


class KnowledgeRetrievalUnavailableError(Exception):
    pass


class KnowledgeRetrievalConfigurationError(Exception):
    pass


@dataclass(frozen=True)
class KnowledgeRetrievalResult:
    text: str
    score: float
    metadata: dict[str, Any]


class KnowledgeBaseRetrievalClient(Protocol):
    def retrieve(
        self,
        *,
        knowledge_base_id: str,
        query: str,
        max_results: int,
        metadata_filter: dict[str, Any],
    ) -> list[KnowledgeRetrievalResult]: ...


class BedrockKnowledgeBaseRetrievalClient:
    def __init__(
        self,
        *,
        region_name: str,
        connect_timeout_seconds: int,
        read_timeout_seconds: int,
        client: Any | None = None,
    ) -> None:
        self.client = client or boto3.client(
            "bedrock-agent-runtime",
            region_name=region_name,
            config=Config(
                connect_timeout=connect_timeout_seconds,
                read_timeout=read_timeout_seconds,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        )

    def retrieve(
        self,
        *,
        knowledge_base_id: str,
        query: str,
        max_results: int,
        metadata_filter: dict[str, Any],
    ) -> list[KnowledgeRetrievalResult]:
        try:
            response = self.client.retrieve(
                knowledgeBaseId=knowledge_base_id,
                retrievalQuery={"text": query},
                retrievalConfiguration={
                    "vectorSearchConfiguration": {
                        "numberOfResults": max_results,
                        "filter": metadata_filter,
                    }
                },
            )
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", "ClientError"))
            if code in TRANSIENT_ERROR_CODES:
                raise KnowledgeRetrievalUnavailableError(
                    "Bedrock Knowledge Bases is temporarily unavailable"
                ) from exc
            raise KnowledgeRetrievalConfigurationError(
                "Bedrock Knowledge Base retrieval is not available"
            ) from exc
        except (
            BotoCoreError,
            ConnectionClosedError,
            EndpointConnectionError,
            ReadTimeoutError,
        ) as exc:
            raise KnowledgeRetrievalUnavailableError(
                "Bedrock Knowledge Bases is temporarily unavailable"
            ) from exc

        results: list[KnowledgeRetrievalResult] = []
        raw_results = response.get("retrievalResults", [])
        if not isinstance(raw_results, list):
            return results
        for raw_result in raw_results:
            result = _parse_retrieval_result(raw_result)
            if result is not None:
                results.append(result)
        return results


class KnowledgeRetrievalService:
    def __init__(
        self,
        *,
        repository: DocumentRepository,
        settings: Settings,
        client: KnowledgeBaseRetrievalClient | None = None,
    ) -> None:
        self.repository = repository
        self.settings = settings
        self.client = client or BedrockKnowledgeBaseRetrievalClient(
            region_name=settings.knowledge_base_region,
            connect_timeout_seconds=settings.knowledge_base_connect_timeout_seconds,
            read_timeout_seconds=settings.knowledge_base_read_timeout_seconds,
        )

    def retrieve(
        self,
        *,
        payload: KnowledgeRetrieveRequest,
        auth_context: AuthContext,
    ) -> KnowledgeRetrieveResponse:
        if auth_context.source_app != CRANE_INTELLIGENCE_SOURCE_APP:
            raise KnowledgeRetrievalAccessDeniedError(
                "Credential is not authorized for Crane Intelligence knowledge"
            )
        knowledge_base_id = self.settings.knowledge_base_id
        if not knowledge_base_id:
            raise KnowledgeRetrievalConfigurationError(
                "Knowledge Base retrieval is not configured"
            )

        results = self.client.retrieve(
            knowledge_base_id=knowledge_base_id,
            query=payload.query,
            max_results=payload.max_results,
            metadata_filter=_build_metadata_filter(
                payload=payload,
                tenant_ids=auth_context.tenant_ids,
            ),
        )
        return self._to_response(
            payload=payload,
            auth_context=auth_context,
            results=results,
        )

    def _to_response(
        self,
        *,
        payload: KnowledgeRetrieveRequest,
        auth_context: AuthContext,
        results: list[KnowledgeRetrievalResult],
    ) -> KnowledgeRetrieveResponse:
        candidates: list[tuple[UUID, KnowledgeRetrievalResult]] = []
        for result in results:
            document_id = _document_id_from_metadata(result.metadata)
            if document_id is not None:
                candidates.append((document_id, result))

        documents_by_id = self.repository.list_rag_indexed_by_ids(
            document_ids={document_id for document_id, _ in candidates},
            auth_context=auth_context,
        )
        citations_by_document: dict[UUID, KnowledgeCitation] = {}
        for document_id, result in candidates:
            document = documents_by_id.get(document_id)
            if document is None or document_id in citations_by_document:
                continue
            citations_by_document[document_id] = KnowledgeCitation(
                document_id=document_id,
                title=_citation_title(result.metadata, document.original_filename),
                excerpt=_excerpt(result.text),
                score=_normalized_score(result.score),
                page_number=_page_number(result.metadata),
            )

        citations = sorted(
            citations_by_document.values(),
            key=lambda citation: citation.score,
            reverse=True,
        )[: payload.max_results]
        return KnowledgeRetrieveResponse(query=payload.query, citations=citations)


def _build_metadata_filter(
    *,
    payload: KnowledgeRetrieveRequest,
    tenant_ids: frozenset[str],
) -> dict[str, Any]:
    filters: list[dict[str, Any]] = [
        {
            "equals": {
                "key": "source_app",
                "value": CRANE_INTELLIGENCE_SOURCE_APP,
            }
        },
        {
            "in": {
                "key": "tenant_id",
                "value": sorted(tenant_ids),
            }
        },
    ]
    for key, value in (
        ("document_id", str(payload.document_id) if payload.document_id else None),
        ("project_id", payload.project_id),
        ("asset_id", payload.asset_id),
        ("component_id", payload.component_id),
    ):
        if value is not None:
            filters.append({"equals": {"key": key, "value": value}})
    return {"andAll": filters}


def _parse_retrieval_result(raw_result: object) -> KnowledgeRetrievalResult | None:
    if not isinstance(raw_result, dict):
        return None
    content = raw_result.get("content")
    metadata = raw_result.get("metadata")
    score = raw_result.get("score")
    if (
        not isinstance(content, dict)
        or not isinstance(content.get("text"), str)
        or not isinstance(metadata, dict)
        or not isinstance(score, (float, int))
    ):
        return None
    return KnowledgeRetrievalResult(
        text=content["text"],
        score=float(score),
        metadata=metadata,
    )


def _document_id_from_metadata(metadata: dict[str, Any]) -> UUID | None:
    value = metadata.get("document_id")
    if not isinstance(value, str):
        return None
    try:
        return UUID(value)
    except ValueError:
        return None


def _citation_title(metadata: dict[str, Any], fallback: str) -> str:
    value = metadata.get("document_title")
    if isinstance(value, str):
        normalized = " ".join(value.split())
        if normalized:
            return normalized[:MAX_TITLE_CHARACTERS]
    return fallback


def _excerpt(text: str) -> str:
    return " ".join(text.split())[:MAX_EXCERPT_CHARACTERS]


def _normalized_score(score: float) -> float:
    if not math.isfinite(score):
        return 0.0
    return max(0.0, min(1.0, score))


def _page_number(metadata: dict[str, Any]) -> int | None:
    value = metadata.get("x-amz-bedrock-kb-document-page-number")
    try:
        page_number = int(value)
    except (TypeError, ValueError):
        return None
    return page_number if page_number >= 1 else None
