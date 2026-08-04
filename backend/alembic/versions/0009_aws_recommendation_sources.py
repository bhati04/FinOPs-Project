"""Add AWS recommendation source imports and canonical deduplication."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_aws_recommendation_sources"
down_revision: str | None = "0008_recommendation_pricing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add source provenance, canonical actions, and sync history."""
    op.add_column("recommendations", sa.Column("canonical_action", sa.String(80)))
    op.add_column(
        "recommendations",
        sa.Column(
            "sources",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[\"cloudwise\"]'::json"),
        ),
    )
    op.add_column(
        "recommendations",
        sa.Column(
            "source_metadata",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )
    op.execute(
        """
        UPDATE recommendations
        SET canonical_action = CASE
            WHEN rule_id = 'ebs.unattached_volume' THEN 'delete'
            WHEN rule_id = 'ec2.unassociated_elastic_ip' THEN 'release'
            ELSE rule_id
        END
        """
    )
    op.alter_column("recommendations", "canonical_action", nullable=False)
    op.alter_column("recommendations", "sources", server_default=None)
    op.alter_column("recommendations", "source_metadata", server_default=None)
    op.create_unique_constraint(
        "uq_recommendations_resource_action",
        "recommendations",
        ["organization_id", "inventory_resource_id", "canonical_action"],
    )

    sync_status = sa.Enum(
        "QUEUED",
        "RUNNING",
        "COMPLETED",
        "PARTIAL",
        "FAILED",
        name="recommendation_sync_status",
    )
    sync_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "recommendation_source_syncs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("region", sa.String(30), nullable=False),
        sa.Column("status", sync_status, nullable=False),
        sa.Column("imported_count", sa.Integer(), nullable=False),
        sa.Column("matched_resource_count", sa.Integer(), nullable=False),
        sa.Column("unmatched_resource_count", sa.Integer(), nullable=False),
        sa.Column("deduplicated_count", sa.Integer(), nullable=False),
        sa.Column("completed_sources", sa.JSON(), nullable=False),
        sa.Column("failed_sources", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["aws_account_connections.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("organization_id", "connection_id", "requested_by_user_id"):
        op.create_index(
            f"ix_recommendation_source_syncs_{column}",
            "recommendation_source_syncs",
            [column],
        )
    op.create_index(
        "ix_recommendation_source_syncs_active_connection",
        "recommendation_source_syncs",
        ["connection_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('QUEUED', 'RUNNING')"),
    )


def downgrade() -> None:
    """Remove AWS recommendation import persistence."""
    op.drop_table("recommendation_source_syncs")
    sa.Enum(name="recommendation_sync_status").drop(op.get_bind(), checkfirst=True)
    op.drop_constraint("uq_recommendations_resource_action", "recommendations", type_="unique")
    op.drop_column("recommendations", "source_metadata")
    op.drop_column("recommendations", "sources")
    op.drop_column("recommendations", "canonical_action")
