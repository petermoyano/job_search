from __future__ import annotations

import logging
from typing import Any

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.documents.repository import DocumentRepository
from app.knowledge.ingestion import KnowledgeIngestionService
from app.knowledge.sync import KnowledgeSyncReconciler


LOGGER = logging.getLogger(__name__)
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("app").setLevel(logging.INFO)


def handler(_event: dict[str, Any], _context: Any) -> dict[str, int]:
    settings = get_settings()
    with SessionLocal() as session:
        reconciler = KnowledgeSyncReconciler(
            repository=DocumentRepository(session),
            ingestion_service=KnowledgeIngestionService(settings=settings),
        )
        summary = reconciler.reconcile()

    result = summary.as_dict()
    LOGGER.info("event=knowledge_sync_reconciled summary=%s", result)
    return result
