from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.documents.auth import AuthContext
from app.documents.models import (
    Document,
    DocumentStatus,
    ResumeProfileDraft,
)

from app.knowledge.contracts import (
    CRANE_INTELLIGENCE_SOURCE_APP,
    KNOWLEDGE_BASE_PROCESSING_POLICY,
    KnowledgeSyncStatus,
)


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
        statement = statement.options(selectinload(Document.resume_profile_draft))
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

    def list_knowledge_sync_candidates(self, *, limit: int) -> list[Document]:
        statement = (
            select(Document)
            .where(
                Document.source_app == CRANE_INTELLIGENCE_SOURCE_APP,
                Document.processing_policy == KNOWLEDGE_BASE_PROCESSING_POLICY,
                Document.status == DocumentStatus.PREPROCESSED,
                Document.knowledge_sync_status.in_(
                    [KnowledgeSyncStatus.PENDING, KnowledgeSyncStatus.IN_PROGRESS]
                ),
            )
            .order_by(Document.knowledge_sync_requested_at.asc())
            .limit(limit)
        )
        return list(self.session.scalars(statement).all())

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
        lease_available = (
            processing_started_at is None or processing_started_at <= stale_before
        )
        resume_policy = (
            document.source_app == "job-search"
            and document.processing_policy == "resume"
        )
        claimed = False
        if document.status == DocumentStatus.UPLOADED:
            document.status = DocumentStatus.PROCESSING
            claimed = True
        elif document.status == DocumentStatus.PROCESSING and lease_available:
            claimed = True
        elif resume_policy and lease_available:
            if document.status == DocumentStatus.CLASSIFYING:
                document.status = DocumentStatus.PREPROCESSED
                claimed = True
            elif document.status in {
                DocumentStatus.PREPROCESSED,
                DocumentStatus.ACCEPTED,
                DocumentStatus.DATA_EXTRACTED,
            }:
                claimed = True
        if not claimed:
            return document, False, previous_status
        document.processing_started_at = started_at
        document.error_code = None
        document.error_message = None
        self.session.commit()
        self.session.refresh(document)
        return document, True, previous_status

    def add_draft(self, draft: ResumeProfileDraft) -> ResumeProfileDraft:
        self.session.add(draft)
        self.session.flush()
        return draft

    def get_draft_by_document(
        self,
        *,
        document_id: UUID,
        for_update: bool = False,
    ) -> ResumeProfileDraft | None:
        statement = select(ResumeProfileDraft).where(
            ResumeProfileDraft.document_id == document_id
        )
        if for_update:
            statement = statement.with_for_update()
        return self.session.scalars(statement).one_or_none()

    def get_draft_scoped(
        self,
        *,
        document_id: UUID,
        auth_context: AuthContext,
    ) -> ResumeProfileDraft | None:
        statement = (
            select(ResumeProfileDraft)
            .join(Document, Document.id == ResumeProfileDraft.document_id)
            .where(
                ResumeProfileDraft.document_id == document_id,
                Document.source_app == auth_context.source_app,
                Document.tenant_id.in_(auth_context.tenant_ids),
            )
        )
        return self.session.scalars(statement).one_or_none()

    def get_draft_by_id_scoped(
        self,
        *,
        draft_id: UUID,
        auth_context: AuthContext,
        for_update: bool = False,
    ) -> ResumeProfileDraft | None:
        statement = (
            select(ResumeProfileDraft)
            .join(Document, Document.id == ResumeProfileDraft.document_id)
            .where(
                ResumeProfileDraft.id == draft_id,
                ResumeProfileDraft.source_app == auth_context.source_app,
                ResumeProfileDraft.tenant_id.in_(auth_context.tenant_ids),
                Document.source_app == auth_context.source_app,
                Document.tenant_id.in_(auth_context.tenant_ids),
            )
            .options(joinedload(ResumeProfileDraft.document))
        )
        if for_update:
            statement = statement.with_for_update()
        return self.session.scalars(statement).one_or_none()

    def list_recent_profile_documents(
        self,
        *,
        profile_id: str,
        auth_context: AuthContext,
        limit: int = 20,
    ) -> list[Document]:
        statement = (
            select(Document)
            .where(
                Document.source_app == auth_context.source_app,
                Document.tenant_id.in_(auth_context.tenant_ids),
                Document.processing_policy == "resume",
                Document.context["profile_id"].as_string() == profile_id,
            )
            .options(selectinload(Document.resume_profile_draft))
            .order_by(Document.created_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(statement).all())

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

    def refresh(self, document: Document) -> None:
        self.session.refresh(document)
