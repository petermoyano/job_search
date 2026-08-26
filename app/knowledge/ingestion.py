from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from typing import Any, Protocol

import boto3  # type: ignore[import-untyped]
from botocore.config import Config
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ConnectionClosedError,
    EndpointConnectionError,
    ReadTimeoutError,
)
from pydantic import ValidationError

from app.core.config import Settings
from app.documents.models import Document, now_utc
from app.documents.storage import DocumentStorage, StorageUnavailableError
from app.knowledge.contracts import (
    CRANE_INTELLIGENCE_SOURCE_APP,
    KNOWLEDGE_BASE_PROCESSING_POLICY,
    KnowledgeDocumentContext,
    KnowledgeSyncStatus,
)


TRANSIENT_ERROR_CODES = {
    "InternalServerException",
    "ServiceQuotaExceededException",
    "ServiceUnavailableException",
    "ThrottlingException",
    "TooManyRequestsException",
}


class KnowledgeIngestionTransientError(Exception):
    pass


class KnowledgeIngestionPermanentError(Exception):
    def __init__(self, *, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message


class KnowledgeBaseIngestionClient(Protocol):
    def start_ingestion_job(
        self,
        *,
        knowledge_base_id: str,
        data_source_id: str,
        client_token: str,
        description: str,
    ) -> str | None: ...


@dataclass(frozen=True)
class KnowledgeIngestionRequest:
    sidecar_key: str
    status: KnowledgeSyncStatus
    ingestion_job_id: str | None
    requested_at: datetime


class BedrockKnowledgeBaseIngestionClient:
    def __init__(
        self,
        *,
        region_name: str,
        connect_timeout_seconds: int,
        read_timeout_seconds: int,
        client: Any | None = None,
    ) -> None:
        self.client = client or boto3.client(
            "bedrock-agent",
            region_name=region_name,
            config=Config(
                connect_timeout=connect_timeout_seconds,
                read_timeout=read_timeout_seconds,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        )

    def start_ingestion_job(
        self,
        *,
        knowledge_base_id: str,
        data_source_id: str,
        client_token: str,
        description: str,
    ) -> str | None:
        try:
            response = self.client.start_ingestion_job(
                knowledgeBaseId=knowledge_base_id,
                dataSourceId=data_source_id,
                clientToken=client_token,
                description=description,
            )
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", "ClientError"))
            if code == "ConflictException":
                return None
            if code in TRANSIENT_ERROR_CODES:
                raise KnowledgeIngestionTransientError(
                    "Bedrock Knowledge Bases is temporarily unavailable"
                ) from exc
            raise KnowledgeIngestionPermanentError(
                code=code,
                message="Bedrock Knowledge Bases rejected the ingestion request",
            ) from exc
        except (
            BotoCoreError,
            ConnectionClosedError,
            EndpointConnectionError,
            ReadTimeoutError,
        ) as exc:
            raise KnowledgeIngestionTransientError(
                "Bedrock Knowledge Bases is temporarily unavailable"
            ) from exc

        job = response.get("ingestionJob")
        job_id = job.get("ingestionJobId") if isinstance(job, dict) else None
        if not isinstance(job_id, str) or not job_id:
            raise KnowledgeIngestionTransientError(
                "Bedrock Knowledge Bases did not return an ingestion job ID"
            )
        return job_id


class KnowledgeIngestionService:
    def __init__(
        self,
        *,
        storage: DocumentStorage,
        settings: Settings,
        client: KnowledgeBaseIngestionClient | None = None,
    ) -> None:
        self.storage = storage
        self.settings = settings
        self.client = client or BedrockKnowledgeBaseIngestionClient(
            region_name=settings.knowledge_base_region,
            connect_timeout_seconds=settings.knowledge_base_connect_timeout_seconds,
            read_timeout_seconds=settings.knowledge_base_read_timeout_seconds,
        )

    def request_sync(
        self,
        *,
        document: Document,
        document_sha256: str,
    ) -> KnowledgeIngestionRequest:
        self._validate_document_scope(document)
        sidecar_key, body = build_metadata_sidecar(
            document=document,
            document_sha256=document_sha256,
        )
        try:
            self.storage.write_object(
                bucket=document.s3_bucket,
                key=sidecar_key,
                body=body,
                content_type="application/json",
            )
        except StorageUnavailableError as exc:
            raise KnowledgeIngestionTransientError(
                "Could not write the Bedrock metadata sidecar"
            ) from exc

        if (
            not self.settings.knowledge_base_id
            or not self.settings.knowledge_base_data_source_id
        ):
            raise KnowledgeIngestionPermanentError(
                code="KNOWLEDGE_BASE_NOT_CONFIGURED",
                message="Knowledge Base ingestion is not configured",
            )

        job_id = self.client.start_ingestion_job(
            knowledge_base_id=self.settings.knowledge_base_id,
            data_source_id=self.settings.knowledge_base_data_source_id,
            client_token=_ingestion_client_token(
                document_id=str(document.id),
                document_sha256=document_sha256,
            ),
            description=f"Sync Crane Intelligence document {document.id}",
        )
        return KnowledgeIngestionRequest(
            sidecar_key=sidecar_key,
            status=(
                KnowledgeSyncStatus.IN_PROGRESS
                if job_id is not None
                else KnowledgeSyncStatus.PENDING
            ),
            ingestion_job_id=job_id,
            requested_at=now_utc(),
        )

    @staticmethod
    def _validate_document_scope(document: Document) -> None:
        if (
            document.source_app != CRANE_INTELLIGENCE_SOURCE_APP
            or document.processing_policy != KNOWLEDGE_BASE_PROCESSING_POLICY
        ):
            raise KnowledgeIngestionPermanentError(
                code="KNOWLEDGE_BASE_SCOPE_INVALID",
                message="Document is not eligible for Knowledge Base ingestion",
            )


def build_metadata_sidecar(
    *,
    document: Document,
    document_sha256: str,
) -> tuple[str, bytes]:
    knowledge_context = _knowledge_context(document)
    attributes = {
        "document_id": str(document.id),
        "tenant_id": document.tenant_id,
        "source_app": document.source_app,
        "project_id": document.project_id,
        "asset_id": knowledge_context.asset_id,
        "component_id": knowledge_context.component_id,
        "document_type": knowledge_context.document_type.value,
        "document_title": knowledge_context.document_title
        or document.original_filename,
        "language": knowledge_context.language,
        "sha256": document_sha256,
    }
    metadata_attributes = {
        key: value for key, value in attributes.items() if value is not None
    }
    body = json.dumps(
        {"metadataAttributes": metadata_attributes},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(body) > 10 * 1024:
        raise KnowledgeIngestionPermanentError(
            code="KNOWLEDGE_METADATA_TOO_LARGE",
            message="Knowledge Base metadata exceeds the 10 KiB sidecar limit",
        )
    return f"{document.s3_key}.metadata.json", body


def _knowledge_context(document: Document) -> KnowledgeDocumentContext:
    context = document.context or {}
    raw_knowledge = context.get("knowledge")
    try:
        return KnowledgeDocumentContext.model_validate(raw_knowledge)
    except ValidationError as exc:
        raise KnowledgeIngestionPermanentError(
            code="KNOWLEDGE_METADATA_INVALID",
            message="Document Knowledge Base metadata is invalid",
        ) from exc


def _ingestion_client_token(*, document_id: str, document_sha256: str) -> str:
    token_hash = sha256(f"{document_id}:{document_sha256}".encode("utf-8")).hexdigest()
    normalized_document_id = document_id.replace("-", "")
    return f"crane-document-{normalized_document_id}-{token_hash[:32]}"
