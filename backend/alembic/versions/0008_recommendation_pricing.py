"""Add verified pricing provenance to recommendations."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_recommendation_pricing"
down_revision: str | None = "0007_recommendations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add pricing state, source metadata, and inspectable inputs."""
    pricing_status = sa.Enum(
        "AVAILABLE",
        "STALE",
        "UNAVAILABLE",
        name="recommendation_pricing_status",
    )
    pricing_status.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "recommendations",
        sa.Column(
            "pricing_status",
            pricing_status,
            nullable=False,
            server_default="UNAVAILABLE",
        ),
    )
    op.add_column("recommendations", sa.Column("pricing_source", sa.String(40)))
    op.add_column("recommendations", sa.Column("pricing_version", sa.String(80)))
    op.add_column(
        "recommendations",
        sa.Column("pricing_effective_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "recommendations",
        sa.Column("pricing_retrieved_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "recommendations",
        sa.Column("pricing_unavailable_reason", sa.String(80)),
    )
    op.add_column(
        "recommendations",
        sa.Column(
            "calculation_inputs",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.alter_column("recommendations", "pricing_status", server_default=None)
    op.alter_column("recommendations", "calculation_inputs", server_default=None)


def downgrade() -> None:
    """Remove recommendation pricing provenance."""
    for column in (
        "calculation_inputs",
        "pricing_unavailable_reason",
        "pricing_retrieved_at",
        "pricing_effective_at",
        "pricing_version",
        "pricing_source",
        "pricing_status",
    ):
        op.drop_column("recommendations", column)
    sa.Enum(name="recommendation_pricing_status").drop(op.get_bind(), checkfirst=True)
