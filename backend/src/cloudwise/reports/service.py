"""Tenant-scoped report generation and schedule application service."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from celery import Celery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cloudwise.aws_accounts.models import AWSAccountConnection
from cloudwise.core.config import Settings
from cloudwise.reports.models import (
    AuditEvent,
    GeneratedReport,
    ReportFrequency,
    ReportSchedule,
    ReportStatus,
)
from cloudwise.reports.schemas import (
    AuditEventResponse,
    ReportCreate,
    ReportResponse,
    ReportScheduleCreate,
    ReportScheduleResponse,
)


class ReportDispatchError(RuntimeError):
    """A persisted report could not be sent to the worker."""


class ReportService:
    """Create reports and schedules without crossing tenant boundaries."""

    def __init__(
        self,
        session: AsyncSession,
        celery_app: Celery,
        settings: Settings,
    ) -> None:
        self._session = session
        self._celery_app = celery_app
        self._settings = settings

    async def create_report(
        self, organization_id: UUID, user_id: UUID, payload: ReportCreate
    ) -> ReportResponse:
        await self._validate_connection(organization_id, payload.connection_id)
        now = datetime.now(UTC)
        report = GeneratedReport(
            organization_id=organization_id,
            requested_by_user_id=user_id,
            connection_id=payload.connection_id,
            schedule_id=None,
            report_type=payload.report_type,
            report_format=payload.report_format,
            status=ReportStatus.QUEUED,
            period_start=payload.period_start,
            period_end=payload.period_end,
            storage_key=None,
            content_type=None,
            byte_size=None,
            checksum_sha256=None,
            error_code=None,
            expires_at=now + timedelta(days=self._settings.report_retention_days),
            created_at=now,
            started_at=None,
            completed_at=None,
        )
        self._session.add(report)
        await self._session.commit()
        try:
            self._celery_app.send_task("cloudwise.reports.generate_report", args=[str(report.id)])
        except Exception as exc:
            report.status = ReportStatus.FAILED
            report.error_code = "DISPATCH_FAILED"
            report.completed_at = datetime.now(UTC)
            await self._session.commit()
            raise ReportDispatchError("The report worker could not accept the job") from exc
        return self.report_response(report)

    async def list_reports(self, organization_id: UUID) -> list[ReportResponse]:
        reports = (
            await self._session.scalars(
                select(GeneratedReport)
                .where(GeneratedReport.organization_id == organization_id)
                .order_by(GeneratedReport.created_at.desc())
            )
        ).all()
        return [self.report_response(report) for report in reports]

    async def get_report(self, organization_id: UUID, report_id: UUID) -> GeneratedReport:
        report = await self._session.scalar(
            select(GeneratedReport).where(
                GeneratedReport.id == report_id,
                GeneratedReport.organization_id == organization_id,
            )
        )
        if report is None:
            raise LookupError("Report was not found")
        return report

    async def create_schedule(
        self,
        organization_id: UUID,
        user_id: UUID,
        payload: ReportScheduleCreate,
    ) -> ReportScheduleResponse:
        await self._validate_connection(organization_id, payload.connection_id)
        now = datetime.now(UTC)
        schedule = ReportSchedule(
            organization_id=organization_id,
            created_by_user_id=user_id,
            connection_id=payload.connection_id,
            name=payload.name,
            report_type=payload.report_type,
            report_format=payload.report_format,
            frequency=payload.frequency,
            recipients=payload.recipients,
            enabled=True,
            next_run_at=next_run(now, payload.frequency),
            last_run_at=None,
            created_at=now,
            updated_at=now,
        )
        self._session.add(schedule)
        await self._session.commit()
        return self.schedule_response(schedule)

    async def list_schedules(self, organization_id: UUID) -> list[ReportScheduleResponse]:
        schedules = (
            await self._session.scalars(
                select(ReportSchedule)
                .where(ReportSchedule.organization_id == organization_id)
                .order_by(ReportSchedule.created_at.desc())
            )
        ).all()
        return [self.schedule_response(schedule) for schedule in schedules]

    async def set_schedule_enabled(
        self, organization_id: UUID, schedule_id: UUID, enabled: bool
    ) -> ReportScheduleResponse:
        schedule = await self._session.scalar(
            select(ReportSchedule).where(
                ReportSchedule.id == schedule_id,
                ReportSchedule.organization_id == organization_id,
            )
        )
        if schedule is None:
            raise LookupError("Report schedule was not found")
        now = datetime.now(UTC)
        schedule.enabled = enabled
        schedule.updated_at = now
        if enabled:
            schedule.next_run_at = next_run(now, schedule.frequency)
        await self._session.commit()
        return self.schedule_response(schedule)

    async def list_audit_events(
        self,
        organization_id: UUID,
        limit: int,
        action: str | None,
    ) -> list[AuditEventResponse]:
        query = select(AuditEvent).where(AuditEvent.organization_id == organization_id)
        if action:
            query = query.where(AuditEvent.action == action)
        events = (
            await self._session.scalars(query.order_by(AuditEvent.created_at.desc()).limit(limit))
        ).all()
        return [
            AuditEventResponse(
                id=event.id,
                actor_user_id=event.actor_user_id,
                action=event.action,
                entity_type=event.entity_type,
                outcome=event.outcome,
                correlation_id=event.correlation_id,
                context=event.context,
                created_at=event.created_at,
            )
            for event in events
        ]

    async def _validate_connection(self, organization_id: UUID, connection_id: UUID | None) -> None:
        if connection_id is None:
            return
        found = await self._session.scalar(
            select(AWSAccountConnection.id).where(
                AWSAccountConnection.id == connection_id,
                AWSAccountConnection.organization_id == organization_id,
            )
        )
        if found is None:
            raise LookupError("AWS account connection was not found")

    @staticmethod
    def report_response(report: GeneratedReport) -> ReportResponse:
        return ReportResponse(
            id=report.id,
            connection_id=report.connection_id,
            schedule_id=report.schedule_id,
            report_type=report.report_type,
            report_format=report.report_format,
            status=report.status,
            period_start=report.period_start,
            period_end=report.period_end,
            content_type=report.content_type,
            byte_size=report.byte_size,
            checksum_sha256=report.checksum_sha256,
            error_code=report.error_code,
            expires_at=report.expires_at,
            created_at=report.created_at,
            started_at=report.started_at,
            completed_at=report.completed_at,
        )

    @staticmethod
    def schedule_response(schedule: ReportSchedule) -> ReportScheduleResponse:
        return ReportScheduleResponse(
            id=schedule.id,
            connection_id=schedule.connection_id,
            name=schedule.name,
            report_type=schedule.report_type,
            report_format=schedule.report_format,
            frequency=schedule.frequency,
            recipients=schedule.recipients,
            enabled=schedule.enabled,
            next_run_at=schedule.next_run_at,
            last_run_at=schedule.last_run_at,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
        )


def next_run(now: datetime, frequency: ReportFrequency) -> datetime:
    """Calculate the next UTC run without locale-dependent calendar state."""
    if frequency is ReportFrequency.DAILY:
        return now + timedelta(days=1)
    if frequency is ReportFrequency.WEEKLY:
        return now + timedelta(days=7)
    month = now.month + 1
    year = now.year
    if month == 13:
        month = 1
        year += 1
    return now.replace(year=year, month=month, day=1)
