"""Persistence for generated reports, schedules, notifications, and audit events."""

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from cloudwise.core.database import Base


class ReportType(StrEnum):
    """Supported bounded report datasets."""

    EXECUTIVE_SUMMARY = "executive_summary"
    COST_DETAIL = "cost_detail"
    RECOMMENDATIONS = "recommendations"


class ReportFormat(StrEnum):
    """Downloadable report encodings."""

    CSV = "csv"
    PDF = "pdf"


class ReportStatus(StrEnum):
    """Asynchronous report lifecycle."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class ReportFrequency(StrEnum):
    """Supported calendar schedule frequencies."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class NotificationStatus(StrEnum):
    """Email delivery outcome."""

    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


class ReportSchedule(Base):
    """Database-driven recurring report definition."""

    __tablename__ = "report_schedules"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    connection_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("aws_account_connections.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    report_type: Mapped[ReportType] = mapped_column(Enum(ReportType, name="report_type"))
    report_format: Mapped[ReportFormat] = mapped_column(Enum(ReportFormat, name="report_format"))
    frequency: Mapped[ReportFrequency] = mapped_column(
        Enum(ReportFrequency, name="report_frequency")
    )
    recipients: Mapped[list[str]] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(Boolean, index=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GeneratedReport(Base):
    """Metadata for a generated report object."""

    __tablename__ = "generated_reports"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    requested_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    connection_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("aws_account_connections.id", ondelete="CASCADE"), index=True
    )
    schedule_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("report_schedules.id", ondelete="SET NULL"), index=True
    )
    report_type: Mapped[ReportType] = mapped_column(Enum(ReportType, name="report_type"))
    report_format: Mapped[ReportFormat] = mapped_column(Enum(ReportFormat, name="report_format"))
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, name="report_status"), index=True
    )
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    storage_key: Mapped[str | None] = mapped_column(String(1024))
    content_type: Mapped[str | None] = mapped_column(String(120))
    byte_size: Mapped[int | None]
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(80))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReportNotification(Base):
    """Append-only delivery record for a scheduled report recipient."""

    __tablename__ = "report_notifications"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    report_id: Mapped[UUID] = mapped_column(
        ForeignKey("generated_reports.id", ondelete="CASCADE"), index=True
    )
    recipient: Mapped[str] = mapped_column(String(320))
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, name="notification_status")
    )
    provider: Mapped[str] = mapped_column(String(40))
    error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    """Append-only, organization-scoped record of authenticated mutations."""

    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    actor_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    action: Mapped[str] = mapped_column(String(120), index=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    outcome: Mapped[str] = mapped_column(String(40))
    correlation_id: Mapped[UUID] = mapped_column(index=True)
    context: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
