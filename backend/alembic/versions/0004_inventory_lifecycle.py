"""Add inactive-resource inventory history."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_inventory_lifecycle"
down_revision: str | None = "0003_inventory_scans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Track whether a previously discovered resource remains visible."""
    op.add_column(
        "inventory_scans",
        sa.Column(
            "failed_services",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.alter_column("inventory_scans", "failed_services", server_default=None)
    op.add_column(
        "inventory_resources",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "inventory_resources",
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "inventory_resources",
        sa.Column("inactive_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_inventory_resources_is_active",
        "inventory_resources",
        ["is_active"],
        unique=False,
    )
    op.alter_column("inventory_resources", "is_active", server_default=None)
    op.alter_column("inventory_resources", "last_seen_at", server_default=None)


def downgrade() -> None:
    """Remove inactive-resource history fields."""
    op.drop_index("ix_inventory_resources_is_active", table_name="inventory_resources")
    op.drop_column("inventory_resources", "inactive_at")
    op.drop_column("inventory_resources", "last_seen_at")
    op.drop_column("inventory_resources", "is_active")
    op.drop_column("inventory_scans", "failed_services")
