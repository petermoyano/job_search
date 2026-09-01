"""add radar quality review outbox

Revision ID: 0009_radar_quality_reviews
Revises: 0008_radar_soft_delete
Create Date: 2026-08-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009_radar_quality_reviews"
down_revision = "0008_radar_soft_delete"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "radar_quality_reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("opportunity_id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=255), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("rubric_version", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("verdict", sa.String(length=10), nullable=True),
        sa.Column("quality_score", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("rationale", sa.JSON(), nullable=False),
        sa.Column("risks", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["radar_opportunities.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["radar_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "opportunity_id",
            "profile_id",
            "rubric_version",
            name="uq_radar_quality_review_opportunity_profile_rubric",
        ),
    )
    op.create_index(
        "ix_radar_quality_reviews_opportunity_id",
        "radar_quality_reviews",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        "ix_radar_quality_reviews_profile_id",
        "radar_quality_reviews",
        ["profile_id"],
        unique=False,
    )
    op.create_index(
        "ix_radar_quality_reviews_run_id",
        "radar_quality_reviews",
        ["run_id"],
        unique=False,
    )
    op.create_table(
        "radar_quality_review_outbox",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("delivery_attempts", sa.Integer(), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["review_id"], ["radar_quality_reviews.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_id", name="uq_radar_quality_review_outbox_review"),
    )
    op.create_index(
        "ix_radar_quality_review_outbox_review_id",
        "radar_quality_review_outbox",
        ["review_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_radar_quality_review_outbox_review_id",
        table_name="radar_quality_review_outbox",
    )
    op.drop_table("radar_quality_review_outbox")
    op.drop_index(
        "ix_radar_quality_reviews_run_id",
        table_name="radar_quality_reviews",
    )
    op.drop_index(
        "ix_radar_quality_reviews_profile_id",
        table_name="radar_quality_reviews",
    )
    op.drop_index(
        "ix_radar_quality_reviews_opportunity_id",
        table_name="radar_quality_reviews",
    )
    op.drop_table("radar_quality_reviews")
