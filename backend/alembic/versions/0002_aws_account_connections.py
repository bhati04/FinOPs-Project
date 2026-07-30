"""Create organization-scoped AWS account connections."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_aws_account_connections"
down_revision: str | None = "0001_identity_organizations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create encrypted AWS connection persistence."""
    status = sa.Enum("PENDING", "VERIFIED", "FAILED", name="aws_connection_status")
    op.create_table(
        "aws_account_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("alias", sa.String(length=120), nullable=False),
        sa.Column("expected_account_id", sa.String(length=12), nullable=False),
        sa.Column("role_arn", sa.String(length=2048), nullable=False),
        sa.Column("encrypted_external_id", sa.LargeBinary(), nullable=False),
        sa.Column("status", status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_aws_account_connections_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_aws_account_connections")),
        sa.UniqueConstraint(
            "organization_id",
            "role_arn",
            name="uq_aws_account_connections_organization_id",
        ),
    )
    op.create_index(
        op.f("ix_aws_account_connections_organization_id"),
        "aws_account_connections",
        ["organization_id"],
    )


def downgrade() -> None:
    """Remove AWS connection persistence."""
    op.drop_table("aws_account_connections")
    sa.Enum(name="aws_connection_status").drop(op.get_bind(), checkfirst=True)
