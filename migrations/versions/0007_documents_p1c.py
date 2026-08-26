"""add Knowledge Base ingestion tracking to documents

Revision ID: 0007_documents_p1c
Revises: 0006_documents_p1b
Create Date: 2026-08-25
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_documents_p1c"
down_revision = "0006_documents_p1b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("knowledge_sync_status", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("knowledge_ingestion_job_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column(
            "knowledge_sync_requested_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "knowledge_sync_completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_documents_knowledge_sync_status",
        "documents",
        ["knowledge_sync_status", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_documents_knowledge_sync_status", table_name="documents")
    op.drop_column("documents", "knowledge_sync_completed_at")
    op.drop_column("documents", "knowledge_sync_requested_at")
    op.drop_column("documents", "knowledge_ingestion_job_id")
    op.drop_column("documents", "knowledge_sync_status")
