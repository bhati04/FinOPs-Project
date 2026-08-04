"""Public report, schedule, notification, and audit schemas."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from cloudwise.reports.models import (
    ReportFormat,
    ReportFrequency,
    ReportStatus,
    ReportType,
)


class ReportCreate(BaseModel):
    """Validated on-demand report request."""

    report_type: ReportType
    report_format: ReportFormat
    connection_id: UUID | None = None
    period_start: date
    period_end: date

    @model_validator(mode="after")
    def validate_period(self) -> "ReportCreate":
        if self.period_end < self.period_start:
            raise ValueError("period_end must be on or after period_start")
        if (self.period_end - self.period_start).days > 366:
            raise ValueError("report period cannot exceed 366 days")
        return self


class ReportResponse(BaseModel):
    """Safe generated report metadata."""

    id: UUID
    connection_id: UUID | None
    schedule_id: UUID | None
    report_type: ReportType
    report_format: ReportFormat
    status: ReportStatus
    period_start: date
    period_end: date
    content_type: str | None
    byte_size: int | None
    checksum_sha256: str | None
    error_code: str | None
    expires_at: datetime
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ReportScheduleCreate(BaseModel):
    """Validated recurring report definition."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=160)
    report_type: ReportType
    report_format: ReportFormat
    frequency: ReportFrequency
    connection_id: UUID | None = None
    recipients: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("recipients")
    @classmethod
    def validate_recipients(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            recipient = value.strip().lower()
            if len(recipient) > 320 or recipient.count("@") != 1:
                raise ValueError("each recipient must be a valid email address")
            normalized.append(recipient)
        return list(dict.fromkeys(normalized))


class ReportScheduleUpdate(BaseModel):
    """Safe schedule activation change."""

    enabled: bool


class ReportScheduleResponse(BaseModel):
    """Organization-scoped recurring report state."""

    id: UUID
    connection_id: UUID | None
    name: str
    report_type: ReportType
    report_format: ReportFormat
    frequency: ReportFrequency
    recipients: list[str]
    enabled: bool
    next_run_at: datetime
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AuditEventResponse(BaseModel):
    """Append-only audit record visible to organization administrators."""

    id: UUID
    actor_user_id: UUID
    action: str
    entity_type: str
    outcome: str
    correlation_id: UUID
    context: dict[str, object]
    created_at: datetime
