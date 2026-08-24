from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.documents.processing import (
    DocumentProcessingService,
    TransientProcessingError,
)
from app.documents.queue import DocumentProcessingMessage
from app.documents.repository import DocumentRepository
from app.documents.storage import get_document_storage


LOGGER = logging.getLogger(__name__)
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("app").setLevel(logging.INFO)


def handler(event: dict[str, Any], _context: Any) -> dict[str, list[dict[str, str]]]:
    failures: list[dict[str, str]] = []
    records = event.get("Records", [])
    if not isinstance(records, list):
        records = []

    for record in records:
        message_id = str(record.get("messageId", ""))
        LOGGER.info(
            "event=document_processing_message_received message_id=%s",
            message_id,
        )
        try:
            body = record.get("body")
            if not isinstance(body, str):
                raise ValueError("SQS record body must be a string")
            message = DocumentProcessingMessage.model_validate_json(body)
        except (ValidationError, ValueError):
            LOGGER.warning(
                "event=document_processing_failed_permanent message_id=%s "
                "error_code=INVALID_MESSAGE",
                message_id,
            )
            continue

        try:
            with SessionLocal() as session:
                service = DocumentProcessingService(
                    repository=DocumentRepository(session),
                    storage=get_document_storage(),
                    settings=get_settings(),
                )
                service.process(document_id=message.document_id)
        except TransientProcessingError:
            LOGGER.exception(
                "event=document_processing_failed_transient document_id=%s "
                "message_id=%s",
                message.document_id,
                message_id,
            )
            failures.append({"itemIdentifier": message_id})
        except Exception:
            LOGGER.exception(
                "event=document_processing_failed_transient document_id=%s "
                "message_id=%s error_code=UNEXPECTED",
                message.document_id,
                message_id,
            )
            failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": failures}
