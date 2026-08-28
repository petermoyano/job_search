"""add profile-scoped radar opportunity soft deletes

Revision ID: 0008_radar_soft_delete
Revises: 0007_documents_p1c
Create Date: 2026-08-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_radar_soft_delete"
down_revision = "0007_documents_p1c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "radar_opportunity_deletions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("opportunity_id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=255), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["opportunity_id"],
            ["radar_opportunities.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "opportunity_id",
            "profile_id",
            name="uq_radar_opportunity_deletions_opportunity_profile",
        ),
    )
    op.create_index(
        "ix_radar_opportunity_deletions_opportunity_id",
        "radar_opportunity_deletions",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        "ix_radar_opportunity_deletions_profile_id",
        "radar_opportunity_deletions",
        ["profile_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_radar_opportunity_deletions_profile_id",
        table_name="radar_opportunity_deletions",
    )
    op.drop_index(
        "ix_radar_opportunity_deletions_opportunity_id",
        table_name="radar_opportunity_deletions",
    )
    op.drop_table("radar_opportunity_deletions")
