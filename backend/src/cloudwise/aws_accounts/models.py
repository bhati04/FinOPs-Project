"""AWS account connection persistence."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from cloudwise.core.database import Base


class ConnectionStatus(StrEnum):
    """AWS connection lifecycle."""

    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"


class AWSAccountConnection(Base):
    """Organization-scoped customer role connection."""

    __tablename__ = "aws_account_connections"
    __table_args__ = (UniqueConstraint("organization_id", "role_arn"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    alias: Mapped[str] = mapped_column(String(120))
    expected_account_id: Mapped[str] = mapped_column(String(12))
    role_arn: Mapped[str] = mapped_column(String(2048))
    encrypted_external_id: Mapped[bytes] = mapped_column(LargeBinary)
    status: Mapped[ConnectionStatus] = mapped_column(
        Enum(ConnectionStatus, name="aws_connection_status")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
