"""Persisted inventory scan and resource models."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    JSON,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from cloudwise.core.database import Base


class ScanStatus(StrEnum):
    """Inventory scan lifecycle."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class InventoryScan(Base):
    """One organization-scoped scan attempt."""

    __tablename__ = "inventory_scans"
    __table_args__ = (
        Index(
            "ix_inventory_scans_active_connection",
            "connection_id",
            unique=True,
            postgresql_where=text("status IN ('QUEUED', 'RUNNING')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("aws_account_connections.id", ondelete="CASCADE"), index=True
    )
    region: Mapped[str] = mapped_column(String(30))
    status: Mapped[ScanStatus] = mapped_column(Enum(ScanStatus, name="inventory_scan_status"))
    resource_count: Mapped[int] = mapped_column(default=0)
    error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InventoryResource(Base):
    """Latest normalized resource discovered for one tenant connection."""

    __tablename__ = "inventory_resources"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "connection_id",
            "region",
            "resource_type",
            "resource_id",
            name="uq_inventory_resources_identity",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("aws_account_connections.id", ondelete="CASCADE"), index=True
    )
    scan_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_scans.id", ondelete="CASCADE"), index=True
    )
    region: Mapped[str] = mapped_column(String(30))
    resource_type: Mapped[str] = mapped_column(String(40))
    resource_id: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(String(80))
    details: Mapped[dict[str, object]] = mapped_column(JSON)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
