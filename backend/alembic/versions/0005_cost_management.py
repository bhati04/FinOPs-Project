"""Create Cost Explorer synchronization persistence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_cost_management"
down_revision: str | None = "0004_inventory_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create tenant-scoped cost syncs and aggregates."""
    sync_status = sa.Enum(
        "QUEUED",
        "RUNNING",
        "COMPLETED",
        "PARTIAL",
        "FAILED",
        name="cost_sync_status",
    )
    granularity = sa.Enum("DAILY", "MONTHLY", name="cost_granularity")
    grouping = sa.Enum("SERVICE_REGION", "USAGE_TYPE", "TAG", name="cost_grouping")
    op.create_table(
        "cost_syncs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("status", sync_status, nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("failed_facets", sa.JSON(), nullable=False),
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
        "ix_cost_syncs_active_connection",
        "cost_syncs",
        ["connection_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('QUEUED', 'RUNNING')"),
    )
    op.create_table(
        "cost_aggregates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("sync_id", sa.Uuid(), nullable=False),
        sa.Column("granularity", granularity, nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("grouping", grouping, nullable=False),
        sa.Column("service", sa.String(255), nullable=False),
        sa.Column("region", sa.String(80), nullable=False),
        sa.Column("usage_type", sa.String(255), nullable=False),
        sa.Column("tag_key", sa.String(128), nullable=False),
        sa.Column("tag_value", sa.String(255), nullable=False),
        sa.Column("amount", sa.Numeric(20, 8), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["aws_account_connections.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["sync_id"], ["cost_syncs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "connection_id",
            "granularity",
            "period_start",
            "grouping",
            "service",
            "region",
            "usage_type",
            "tag_key",
            "tag_value",
            "currency",
            name="uq_cost_aggregates_dimensions",
        ),
    )
    op.create_table(
        "cost_forecasts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("sync_id", sa.Uuid(), nullable=False),
        sa.Column(
            "granularity",
            postgresql.ENUM(
                "DAILY",
                "MONTHLY",
                name="cost_granularity",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("mean_amount", sa.Numeric(20, 8), nullable=False),
        sa.Column("lower_bound", sa.Numeric(20, 8), nullable=False),
        sa.Column("upper_bound", sa.Numeric(20, 8), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["aws_account_connections.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["sync_id"], ["cost_syncs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "connection_id",
            "granularity",
            "period_start",
            "period_end",
            "currency",
            name="uq_cost_forecasts_period",
        ),
    )


def downgrade() -> None:
    """Remove Cost Explorer synchronization persistence."""
    op.drop_table("cost_forecasts")
    op.drop_table("cost_aggregates")
    op.drop_table("cost_syncs")
    sa.Enum(name="cost_grouping").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="cost_granularity").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="cost_sync_status").drop(op.get_bind(), checkfirst=True)
