"""Persisted Cost Explorer synchronization models."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from cloudwise.core.database import Base


class CostSyncStatus(StrEnum):
    """Cost synchronization lifecycle."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class CostGranularity(StrEnum):
    """Supported Cost Explorer aggregation periods."""

    DAILY = "daily"
    MONTHLY = "monthly"


class CostGrouping(StrEnum):
    """Supported Cost Explorer grouping views."""

    SERVICE_REGION = "service_region"
    USAGE_TYPE = "usage_type"
    TAG = "tag"


class CostSync(Base):
    """One asynchronous Cost Explorer synchronization."""

    __tablename__ = "cost_syncs"
    __table_args__ = (
        Index(
            "ix_cost_syncs_active_connection",
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
    status: Mapped[CostSyncStatus] = mapped_column(
        Enum(CostSyncStatus, name="cost_sync_status")
    )
    record_count: Mapped[int] = mapped_column(default=0)
    error_code: Mapped[str | None] = mapped_column(String(80))
    failed_facets: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CostAggregate(Base):
    """Idempotent service-and-Region cost aggregate."""

    __tablename__ = "cost_aggregates"
    __table_args__ = (
        UniqueConstraint(
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

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("aws_account_connections.id", ondelete="CASCADE"), index=True
    )
    sync_id: Mapped[UUID] = mapped_column(
        ForeignKey("cost_syncs.id", ondelete="CASCADE"), index=True
    )
    granularity: Mapped[CostGranularity] = mapped_column(
        Enum(CostGranularity, name="cost_granularity")
    )
    period_start: Mapped[date] = mapped_column(Date)
    grouping: Mapped[CostGrouping] = mapped_column(
        Enum(CostGrouping, name="cost_grouping")
    )
    service: Mapped[str] = mapped_column(String(255), default="")
    region: Mapped[str] = mapped_column(String(80), default="")
    usage_type: Mapped[str] = mapped_column(String(255), default="")
    tag_key: Mapped[str] = mapped_column(String(128), default="")
    tag_value: Mapped[str] = mapped_column(String(255), default="")
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    currency: Mapped[str] = mapped_column(String(8))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CostForecast(Base):
    """Persisted Cost Explorer forecast for a customer connection."""

    __tablename__ = "cost_forecasts"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "connection_id",
            "granularity",
            "period_start",
            "period_end",
            "currency",
            name="uq_cost_forecasts_period",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("aws_account_connections.id", ondelete="CASCADE"), index=True
    )
    sync_id: Mapped[UUID] = mapped_column(
        ForeignKey("cost_syncs.id", ondelete="CASCADE"), index=True
    )
    granularity: Mapped[CostGranularity] = mapped_column(
        Enum(CostGranularity, name="cost_granularity")
    )
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    mean_amount: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    lower_bound: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    upper_bound: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    currency: Mapped[str] = mapped_column(String(8))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
