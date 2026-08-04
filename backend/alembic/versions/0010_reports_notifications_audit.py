"""Add reports, schedules, notifications, and immutable audit events."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_reports_notifications_audit"
down_revision: str | None = "0009_aws_recommendation_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(name=name, create_type=False)


def upgrade() -> None:
    """Create Milestone 7 reporting and audit persistence."""
    enums = (
        sa.Enum("EXECUTIVE_SUMMARY", "COST_DETAIL", "RECOMMENDATIONS", name="report_type"),
        sa.Enum("CSV", "PDF", name="report_format"),
        sa.Enum("DAILY", "WEEKLY", "MONTHLY", name="report_frequency"),
        sa.Enum("QUEUED", "RUNNING", "COMPLETED", "FAILED", "EXPIRED", name="report_status"),
        sa.Enum("SENT", "FAILED", "SKIPPED", name="notification_status"),
    )
    for enum in enums:
        enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "report_schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid()),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("report_type", _enum("report_type"), nullable=False),
        sa.Column("report_format", _enum("report_format"), nullable=False),
        sa.Column("frequency", _enum("report_frequency"), nullable=False),
        sa.Column("recipients", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["aws_account_connections.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "organization_id",
        "created_by_user_id",
        "connection_id",
        "enabled",
        "next_run_at",
    ):
        op.create_index(f"ix_report_schedules_{column}", "report_schedules", [column])

    op.create_table(
        "generated_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid()),
        sa.Column("schedule_id", sa.Uuid()),
        sa.Column("report_type", _enum("report_type"), nullable=False),
        sa.Column("report_format", _enum("report_format"), nullable=False),
        sa.Column("status", _enum("report_status"), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("storage_key", sa.String(1024)),
        sa.Column("content_type", sa.String(120)),
        sa.Column("byte_size", sa.Integer()),
        sa.Column("checksum_sha256", sa.String(64)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["aws_account_connections.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["schedule_id"], ["report_schedules.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "organization_id",
        "requested_by_user_id",
        "connection_id",
        "schedule_id",
        "status",
        "expires_at",
    ):
        op.create_index(f"ix_generated_reports_{column}", "generated_reports", [column])

    op.create_table(
        "report_notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("recipient", sa.String(320), nullable=False),
        sa.Column("status", _enum("notification_status"), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_id"], ["generated_reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_report_notifications_organization_id", "report_notifications", ["organization_id"]
    )
    op.create_index("ix_report_notifications_report_id", "report_notifications", ["report_id"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("outcome", sa.String(40), nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "organization_id",
        "actor_user_id",
        "action",
        "entity_type",
        "correlation_id",
        "created_at",
    ):
        op.create_index(f"ix_audit_events_{column}", "audit_events", [column])
    op.execute(
        """
        CREATE FUNCTION cloudwise_reject_audit_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit events are append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_events_append_only
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION cloudwise_reject_audit_mutation()
        """
    )


def downgrade() -> None:
    """Remove Milestone 7 persistence."""
    op.execute("DROP TRIGGER IF EXISTS audit_events_append_only ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS cloudwise_reject_audit_mutation")
    op.drop_table("audit_events")
    op.drop_table("report_notifications")
    op.drop_table("generated_reports")
    op.drop_table("report_schedules")
    for name in (
        "notification_status",
        "report_status",
        "report_frequency",
        "report_format",
        "report_type",
    ):
        sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)
