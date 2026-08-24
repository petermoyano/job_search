from __future__ import annotations

from functools import lru_cache
import json
from typing import Literal, Protocol
from uuid import UUID

from botocore.exceptions import BotoCoreError, ClientError
from pydantic import BaseModel, ConfigDict

from app.core.config import get_settings


class QueueUnavailableError(Exception):
    pass


class DocumentProcessingMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    document_id: UUID


class DocumentProcessingQueue(Protocol):
    def enqueue(self, *, document_id: UUID) -> None: ...


class SqsDocumentProcessingQueue:
    def __init__(self, *, queue_url: str, region_name: str) -> None:
        import boto3  # type: ignore[import-untyped]

        self.queue_url = queue_url
        self.client = boto3.client("sqs", region_name=region_name)

    def enqueue(self, *, document_id: UUID) -> None:
        if not self.queue_url:
            raise QueueUnavailableError("Document processing queue is not configured")
        message = DocumentProcessingMessage(document_id=document_id)
        try:
            self.client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(
                    message.model_dump(mode="json"),
                    separators=(",", ":"),
                ),
            )
        except (BotoCoreError, ClientError) as exc:
            raise QueueUnavailableError(
                "Could not enqueue document processing"
            ) from exc


@lru_cache
def get_document_processing_queue() -> SqsDocumentProcessingQueue:
    settings = get_settings()
    return SqsDocumentProcessingQueue(
        queue_url=settings.document_processing_queue_url,
        region_name=settings.aws_region,
    )
