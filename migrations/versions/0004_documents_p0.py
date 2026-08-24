"""add generic document ingestion metadata

Revision ID: 0004_documents_p0
Revises: 0003_editable_radar_profiles
Create Date: 2026-08-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_documents_p0"
down_revision = "0003_editable_radar_profiles"
branch_labels = None
depends_on = None

DOCUMENT_STATUSES = (
    "PENDING_UPLOAD",
    "UPLOADED",
    "VALIDATING",
    "CLASSIFYING",
    "ACCEPTED",
    "REJECTED",
    "NEEDS_REVIEW",
    "PROCESSING",
    "RAG_INDEXED",
    "DATA_EXTRACTED",
    "COMPLETED",
    "FAILED",
)


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("source_app", sa.String(length=64), nullable=False),
        sa.Column("processing_policy", sa.String(length=100), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("s3_bucket", sa.String(length=255), nullable=False),
        sa.Column("s3_key", sa.String(length=1024), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                *DOCUMENT_STATUSES,
                name="document_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("classification", sa.String(length=255), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("decision", sa.String(length=255), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
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
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("s3_key"),
    )
    op.create_index(
        "ix_documents_tenant_source_created",
        "documents",
        ["tenant_id", "source_app", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_documents_tenant_source_created", table_name="documents")
    op.drop_table("documents")
