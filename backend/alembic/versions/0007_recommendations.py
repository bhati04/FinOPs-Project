"""Create deterministic recommendation persistence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_recommendations"
down_revision: str | None = "0006_resource_metrics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create evaluations, recommendations, and append-only activity."""
    recommendation_status = sa.Enum(
        "OPEN",
        "ACKNOWLEDGED",
        "DISMISSED",
        "RESOLVED",
        name="recommendation_status",
    )
    recommendation_severity = sa.Enum(
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL",
        name="recommendation_severity",
    )
    estimate_type = sa.Enum(
        "EXACT",
        "USAGE_BASED",
        "ADVISORY",
        name="recommendation_estimate_type",
    )
    activity_type = sa.Enum(
        "STATUS_CHANGED",
        "COMMENT",
        name="recommendation_activity_type",
    )
    op.create_table(
        "recommendation_evaluations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=True),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("rule_set_version", sa.String(40), nullable=False),
        sa.Column("evaluated_resource_count", sa.Integer(), nullable=False),
        sa.Column("eligible_recommendation_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["aws_account_connections.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("organization_id", "connection_id", "requested_by_user_id"):
        op.create_index(
            f"ix_recommendation_evaluations_{column}",
            "recommendation_evaluations",
            [column],
        )

    op.create_table(
        "recommendations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("inventory_resource_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_id", sa.Uuid(), nullable=False),
        sa.Column("rule_id", sa.String(100), nullable=False),
        sa.Column("rule_version", sa.String(40), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("severity", recommendation_severity, nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("status", recommendation_status, nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("exclusions", sa.JSON(), nullable=False),
        sa.Column("risk_notes", sa.JSON(), nullable=False),
        sa.Column("verification_steps", sa.JSON(), nullable=False),
        sa.Column("evidence_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("estimate_type", estimate_type, nullable=False),
        sa.Column("current_monthly_cost", sa.Numeric(20, 8), nullable=True),
        sa.Column("estimated_monthly_savings", sa.Numeric(20, 8), nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("calculation_summary", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["aws_account_connections.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["inventory_resource_id"], ["inventory_resources.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_id"], ["recommendation_evaluations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "inventory_resource_id",
            "rule_id",
            name="uq_recommendations_resource_rule",
        ),
    )
    for column in (
        "organization_id",
        "connection_id",
        "inventory_resource_id",
        "evaluation_id",
        "status",
    ):
        op.create_index(f"ix_recommendations_{column}", "recommendations", [column])

    op.create_table(
        "recommendation_activities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("recommendation_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("activity_type", activity_type, nullable=False),
        sa.Column(
            "from_status",
            postgresql.ENUM(
                "OPEN",
                "ACKNOWLEDGED",
                "DISMISSED",
                "RESOLVED",
                name="recommendation_status",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column(
            "to_status",
            postgresql.ENUM(
                "OPEN",
                "ACKNOWLEDGED",
                "DISMISSED",
                "RESOLVED",
                name="recommendation_status",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recommendation_id"], ["recommendations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("organization_id", "recommendation_id", "actor_user_id"):
        op.create_index(
            f"ix_recommendation_activities_{column}",
            "recommendation_activities",
            [column],
        )


def downgrade() -> None:
    """Remove deterministic recommendation persistence."""
    op.drop_table("recommendation_activities")
    op.drop_table("recommendations")
    op.drop_table("recommendation_evaluations")
    sa.Enum(name="recommendation_activity_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="recommendation_estimate_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="recommendation_severity").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="recommendation_status").drop(op.get_bind(), checkfirst=True)
