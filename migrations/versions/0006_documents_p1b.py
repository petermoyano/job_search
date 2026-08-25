"""add resume processing context and profile drafts

Revision ID: 0006_documents_p1b
Revises: 0005_documents_p1a
Create Date: 2026-08-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0006_documents_p1b"
down_revision = "0005_documents_p1a"
branch_labels = None
depends_on = None


def _json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("context", _json_type(), nullable=True),
    )
    op.create_table(
        "resume_profile_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("source_app", sa.String(length=64), nullable=False),
        sa.Column("profile_id", sa.String(length=255), nullable=True),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("payload", _json_type(), nullable=False),
        sa.Column("model_id", sa.String(length=255), nullable=False),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            name="uq_resume_profile_drafts_document_id",
        ),
    )
    op.create_index(
        "ix_resume_profile_drafts_tenant_source",
        "resume_profile_drafts",
        ["tenant_id", "source_app"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_resume_profile_drafts_tenant_source",
        table_name="resume_profile_drafts",
    )
    op.drop_table("resume_profile_drafts")
    op.drop_column("documents", "context")
