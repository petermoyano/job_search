from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.documents.auth import AuthContext
from app.documents.models import Document


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

    def commit(self) -> None:
        self.session.commit()

    def refresh(self, document: Document) -> None:
        self.session.refresh(document)
