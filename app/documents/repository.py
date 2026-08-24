from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.documents.auth import AuthContext
from app.documents.models import Document, DocumentStatus


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, document: Document) -> Document:
        self.session.add(document)
        self.session.flush()
        return document

    def get_scoped(
        self,
        *,
        document_id: UUID,
        auth_context: AuthContext,
        for_update: bool = False,
    ) -> Document | None:
        statement = select(Document).where(
            Document.id == document_id,
            Document.source_app == auth_context.source_app,
            Document.tenant_id.in_(auth_context.tenant_ids),
        )
        if for_update:
            statement = statement.with_for_update()
        return self.session.scalars(statement).one_or_none()

    def get_for_processing(
        self, *, document_id: UUID, for_update: bool = False
    ) -> Document | None:
        statement = select(Document).where(Document.id == document_id)
        if for_update:
            statement = statement.with_for_update()
        return self.session.scalars(statement).one_or_none()

    def claim_for_processing(
        self,
        *,
        document_id: UUID,
        started_at: datetime,
        stale_before: datetime,
    ) -> tuple[Document | None, bool, DocumentStatus | None]:
        document = self.get_for_processing(
            document_id=document_id,
            for_update=True,
        )
        if document is None:
            return None, False, None
        previous_status = document.status
        processing_started_at = document.processing_started_at
        if processing_started_at is not None and processing_started_at.tzinfo is None:
            processing_started_at = processing_started_at.replace(
                tzinfo=started_at.tzinfo
            )
        is_stale = (
            document.status == DocumentStatus.PROCESSING
            and processing_started_at is not None
            and processing_started_at <= stale_before
        )
        if document.status != DocumentStatus.UPLOADED and not is_stale:
            return document, False, previous_status
        document.status = DocumentStatus.PROCESSING
        document.processing_started_at = started_at
        document.error_code = None
        document.error_message = None
        self.session.commit()
        self.session.refresh(document)
        return document, True, previous_status

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

    def refresh(self, document: Document) -> None:
        self.session.refresh(document)
