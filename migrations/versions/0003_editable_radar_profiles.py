"""add editable radar profiles and immutable run snapshots

Revision ID: 0003_editable_radar_profiles
Revises: 0002_radar_feedback_loop
Create Date: 2026-08-12
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_editable_radar_profiles"
down_revision = "0002_radar_feedback_loop"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "radar_profile_configs",
        sa.Column("profile_id", sa.String(length=255), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("profile_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("profile_id"),
    )
    op.add_column(
        "radar_runs",
        sa.Column(
            "profile_snapshot",
            sa.JSON(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("radar_runs", "profile_snapshot")
    op.drop_table("radar_profile_configs")
