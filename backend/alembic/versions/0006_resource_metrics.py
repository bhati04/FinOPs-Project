"""Create tenant-scoped CloudWatch resource metrics."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_resource_metrics"
down_revision: str | None = "0005_cost_management"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create CloudWatch synchronization and datapoint persistence."""
    sync_status = sa.Enum(
        "QUEUED",
        "RUNNING",
        "COMPLETED",
        "PARTIAL",
        "FAILED",
        name="metric_sync_status",
    )
    op.create_table(
        "metric_syncs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("region", sa.String(30), nullable=False),
        sa.Column("status", sync_status, nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("failed_batch_count", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["aws_account_connections.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_metric_syncs_active_connection_region",
        "metric_syncs",
        ["connection_id", "region"],
        unique=True,
        postgresql_where=sa.text("status IN ('QUEUED', 'RUNNING')"),
    )
    op.create_index(
        "ix_metric_syncs_organization_id",
        "metric_syncs",
        ["organization_id"],
    )
    op.create_index(
        "ix_metric_syncs_connection_id",
        "metric_syncs",
        ["connection_id"],
    )
    op.create_table(
        "resource_metrics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("inventory_resource_id", sa.Uuid(), nullable=False),
        sa.Column("sync_id", sa.Uuid(), nullable=False),
        sa.Column("namespace", sa.String(80), nullable=False),
        sa.Column("metric_name", sa.String(120), nullable=False),
        sa.Column("statistic", sa.String(20), nullable=False),
        sa.Column("unit", sa.String(40), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value", sa.Numeric(24, 8), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["aws_account_connections.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["inventory_resource_id"], ["inventory_resources.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["sync_id"], ["metric_syncs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "inventory_resource_id",
            "metric_name",
            "statistic",
            "timestamp",
            name="uq_resource_metrics_datapoint",
        ),
    )
    op.create_index(
        "ix_resource_metrics_organization_id",
        "resource_metrics",
        ["organization_id"],
    )
    op.create_index(
        "ix_resource_metrics_connection_id",
        "resource_metrics",
        ["connection_id"],
    )
    op.create_index(
        "ix_resource_metrics_inventory_resource_id",
        "resource_metrics",
        ["inventory_resource_id"],
    )
    op.create_index(
        "ix_resource_metrics_sync_id",
        "resource_metrics",
        ["sync_id"],
    )
    op.create_index(
        "ix_resource_metrics_timestamp",
        "resource_metrics",
        ["timestamp"],
    )


def downgrade() -> None:
    """Remove CloudWatch metric persistence."""
    op.drop_table("resource_metrics")
    op.drop_table("metric_syncs")
    sa.Enum(name="metric_sync_status").drop(op.get_bind(), checkfirst=True)
