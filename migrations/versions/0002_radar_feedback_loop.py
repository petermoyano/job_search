"""persist radar runs, opportunities, evaluations, and feedback

Revision ID: 0002_radar_feedback_loop
Revises: 0001_initial_schema
Create Date: 2026-07-30
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_radar_feedback_loop"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "radar_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=255), nullable=False),
        sa.Column("profile_version", sa.String(length=100), nullable=False),
        sa.Column("connector", sa.String(length=100), nullable=False),
        sa.Column("requested_limit", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("total_raw", sa.Integer(), nullable=False),
        sa.Column("total_unique", sa.Integer(), nullable=False),
        sa.Column("total_qualified", sa.Integer(), nullable=False),
        sa.Column("total_new", sa.Integer(), nullable=False),
        sa.Column("total_excluded", sa.Integer(), nullable=False),
        sa.Column("source_summaries", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_radar_runs_profile_id"),
        "radar_runs",
        ["profile_id"],
        unique=False,
    )
    op.create_table(
        "radar_opportunities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("identity_key", sa.String(length=1000), nullable=False),
        sa.Column("canonical_url", sa.String(length=1000), nullable=False),
        sa.Column("source_kind", sa.String(length=100), nullable=False),
        sa.Column("source_domain", sa.String(length=255), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("location_text", sa.String(length=500), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("facts", sa.JSON(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_presented_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_url"),
        sa.UniqueConstraint("identity_key"),
    )
    op.create_table(
        "radar_evaluations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("opportunity_id", sa.String(length=36), nullable=False),
        sa.Column("verdict", sa.String(length=50), nullable=False),
        sa.Column("eligible", sa.Boolean(), nullable=False),
        sa.Column("is_new", sa.Boolean(), nullable=False),
        sa.Column("presented", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("role_tier", sa.Integer(), nullable=True),
        sa.Column("facts", sa.JSON(), nullable=False),
        sa.Column("eligibility_checks", sa.JSON(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("positive_signals", sa.JSON(), nullable=False),
        sa.Column("negative_signals", sa.JSON(), nullable=False),
        sa.Column("classifier_version", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["radar_opportunities.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["radar_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "opportunity_id",
            name="uq_radar_evaluation_run_opportunity",
        ),
    )
    op.create_index(
        op.f("ix_radar_evaluations_opportunity_id"),
        "radar_evaluations",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_radar_evaluations_run_id"),
        "radar_evaluations",
        ["run_id"],
        unique=False,
    )
    op.create_table(
        "radar_feedback",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("opportunity_id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["radar_opportunities.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "opportunity_id",
            "profile_id",
            name="uq_radar_feedback_opportunity_profile",
        ),
    )
    op.create_index(
        op.f("ix_radar_feedback_opportunity_id"),
        "radar_feedback",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_radar_feedback_profile_id"),
        "radar_feedback",
        ["profile_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_radar_feedback_profile_id"), table_name="radar_feedback")
    op.drop_index(
        op.f("ix_radar_feedback_opportunity_id"),
        table_name="radar_feedback",
    )
    op.drop_table("radar_feedback")
    op.drop_index(
        op.f("ix_radar_evaluations_run_id"),
        table_name="radar_evaluations",
    )
    op.drop_index(
        op.f("ix_radar_evaluations_opportunity_id"),
        table_name="radar_evaluations",
    )
    op.drop_table("radar_evaluations")
    op.drop_table("radar_opportunities")
    op.drop_index(op.f("ix_radar_runs_profile_id"), table_name="radar_runs")
    op.drop_table("radar_runs")
