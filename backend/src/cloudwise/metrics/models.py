"""Persisted CloudWatch metric synchronization models."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from cloudwise.core.database import Base


class MetricSyncStatus(StrEnum):
    """CloudWatch metric synchronization lifecycle."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class MetricSync(Base):
    """One organization-scoped CloudWatch synchronization."""

    __tablename__ = "metric_syncs"
    __table_args__ = (
        Index(
            "ix_metric_syncs_active_connection_region",
            "connection_id",
            "region",
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
    status: Mapped[MetricSyncStatus] = mapped_column(
        Enum(MetricSyncStatus, name="metric_sync_status")
    )
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    record_count: Mapped[int] = mapped_column(default=0)
    failed_batch_count: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ResourceMetric(Base):
    """One normalized CloudWatch metric datapoint for an inventory resource."""

    __tablename__ = "resource_metrics"
    __table_args__ = (
        UniqueConstraint(
            "inventory_resource_id",
            "metric_name",
            "statistic",
            "timestamp",
            name="uq_resource_metrics_datapoint",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("aws_account_connections.id", ondelete="CASCADE"), index=True
    )
    inventory_resource_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_resources.id", ondelete="CASCADE"), index=True
    )
    sync_id: Mapped[UUID] = mapped_column(
        ForeignKey("metric_syncs.id", ondelete="CASCADE"), index=True
    )
    namespace: Mapped[str] = mapped_column(String(80))
    metric_name: Mapped[str] = mapped_column(String(120))
    statistic: Mapped[str] = mapped_column(String(20))
    unit: Mapped[str] = mapped_column(String(40))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    value: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
