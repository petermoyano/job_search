"""add asynchronous document preprocessing state

Revision ID: 0005_documents_p1a
Revises: 0004_documents_p0
Create Date: 2026-08-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_documents_p1a"
down_revision = "0004_documents_p0"
branch_labels = None
depends_on = None

P0_DOCUMENT_STATUSES = (
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
P1A_DOCUMENT_STATUSES = (
    *P0_DOCUMENT_STATUSES[:8],
    "PREPROCESSED",
    *P0_DOCUMENT_STATUSES[8:],
)


def _status_check(statuses: tuple[str, ...]) -> str:
    values = ", ".join(f"'{status}'" for status in statuses)
    return f"status IN ({values})"


def upgrade() -> None:
    bind = op.get_bind()
    columns = (
        sa.Column(
            "processing_enqueued_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "processing_started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "preprocessed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("documents", recreate="always") as batch_op:
            for column in columns:
                batch_op.add_column(column)
            batch_op.drop_constraint("document_status", type_="check")
            batch_op.create_check_constraint(
                "document_status",
                _status_check(P1A_DOCUMENT_STATUSES),
            )
        return

    for column in columns:
        op.add_column("documents", column)
    op.drop_constraint("document_status", "documents", type_="check")
    op.create_check_constraint(
        "document_status",
        "documents",
        _status_check(P1A_DOCUMENT_STATUSES),
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE documents SET status = 'PROCESSING' "
            "WHERE status = 'PREPROCESSED'"
        )
    )
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("documents", recreate="always") as batch_op:
            batch_op.drop_constraint("document_status", type_="check")
            batch_op.create_check_constraint(
                "document_status",
                _status_check(P0_DOCUMENT_STATUSES),
            )
            batch_op.drop_column("preprocessed_at")
            batch_op.drop_column("processing_started_at")
            batch_op.drop_column("processing_enqueued_at")
        return

    op.drop_constraint("document_status", "documents", type_="check")
    op.create_check_constraint(
        "document_status",
        "documents",
        _status_check(P0_DOCUMENT_STATUSES),
    )
    op.drop_column("documents", "preprocessed_at")
    op.drop_column("documents", "processing_started_at")
    op.drop_column("documents", "processing_enqueued_at")
