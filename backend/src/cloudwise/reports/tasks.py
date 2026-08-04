"""Asynchronous generation, scheduling, delivery, and expiration tasks."""

import hashlib
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cloudwise.core.config import get_settings
from cloudwise.core.database import get_session_factory, run_async_job
from cloudwise.cost_management.models import CostAggregate, CostGranularity, CostGrouping
from cloudwise.recommendations.models import Recommendation, RecommendationStatus
from cloudwise.reports.models import (
    GeneratedReport,
    NotificationStatus,
    ReportFormat,
    ReportFrequency,
    ReportNotification,
    ReportSchedule,
    ReportStatus,
    ReportType,
)
from cloudwise.reports.notifications import build_notification_provider
from cloudwise.reports.rendering import render_csv, render_pdf
from cloudwise.reports.service import next_run
from cloudwise.reports.storage import ReportStorageError, build_report_storage
from cloudwise.scans.models import InventoryResource
from cloudwise.worker import celery_app

logger = structlog.get_logger()


@celery_app.task(name="cloudwise.reports.generate_report")  # type: ignore[untyped-decorator]
def generate_report(report_id: str) -> None:
    """Generate and privately store one report."""
    run_async_job(_generate_report(UUID(report_id)))


@celery_app.task(name="cloudwise.reports.dispatch_due_reports")  # type: ignore[untyped-decorator]
def dispatch_due_reports() -> None:
    """Create jobs for database schedules that are due."""
    run_async_job(_dispatch_due_reports())


@celery_app.task(name="cloudwise.reports.expire_reports")  # type: ignore[untyped-decorator]
def expire_reports() -> None:
    """Delete expired report objects and retain their metadata."""
    run_async_job(_expire_reports())


async def _generate_report(report_id: UUID) -> None:
    settings = get_settings()
    session_factory = get_session_factory()
    async with session_factory() as session:
        report = await session.scalar(
            select(GeneratedReport).where(GeneratedReport.id == report_id)
        )
        if report is None or report.status is not ReportStatus.QUEUED:
            return
        report.status = ReportStatus.RUNNING
        report.started_at = datetime.now(UTC)
        await session.commit()
        try:
            title, columns, rows = await _dataset(session, report)
            if report.report_format is ReportFormat.CSV:
                content = render_csv(columns, rows)
                content_type = "text/csv; charset=utf-8"
                extension = "csv"
            else:
                content = render_pdf(title, columns, rows)
                content_type = "application/pdf"
                extension = "pdf"
            key = f"{settings.report_s3_prefix}/{report.organization_id}/{report.id}.{extension}"
            storage = build_report_storage(settings)
            storage.put(key, content, content_type)
            report.storage_key = key
            report.content_type = content_type
            report.byte_size = len(content)
            report.checksum_sha256 = hashlib.sha256(content).hexdigest()
            report.status = ReportStatus.COMPLETED
            report.completed_at = datetime.now(UTC)
            await _notify(session, report)
            await session.commit()
        except ReportStorageError as exc:
            await session.rollback()
            logger.warning("report_storage_failed")
            await _mark_failed(report_id, str(exc))
        except Exception:
            await session.rollback()
            logger.exception("report_generation_failed")
            await _mark_failed(report_id, "REPORT_GENERATION_FAILED")


async def _dataset(
    session: AsyncSession, report: GeneratedReport
) -> tuple[str, list[str], list[list[str]]]:
    if report.report_type is ReportType.COST_DETAIL:
        cost_detail_query = select(CostAggregate).where(
            CostAggregate.organization_id == report.organization_id,
            CostAggregate.granularity == CostGranularity.DAILY,
            CostAggregate.grouping == CostGrouping.SERVICE_REGION,
            CostAggregate.period_start >= report.period_start,
            CostAggregate.period_start <= report.period_end,
        )
        if report.connection_id:
            cost_detail_query = cost_detail_query.where(
                CostAggregate.connection_id == report.connection_id
            )
        cost_records = (
            await session.scalars(cost_detail_query.order_by(CostAggregate.period_start))
        ).all()
        columns = ["Date", "Service", "Region", "Amount", "Currency"]
        rows = [
            [
                str(item.period_start),
                _cell(item.service),
                _cell(item.region),
                str(item.amount),
                item.currency,
            ]
            for item in cost_records
        ]
        return "CloudWise Cost Detail", columns, rows
    if report.report_type is ReportType.RECOMMENDATIONS:
        start = datetime.combine(report.period_start, time.min, tzinfo=UTC)
        end = datetime.combine(report.period_end + timedelta(days=1), time.min, tzinfo=UTC)
        recommendation_query = (
            select(Recommendation, InventoryResource)
            .join(InventoryResource, InventoryResource.id == Recommendation.inventory_resource_id)
            .where(
                Recommendation.organization_id == report.organization_id,
                Recommendation.updated_at >= start,
                Recommendation.updated_at < end,
            )
        )
        if report.connection_id:
            recommendation_query = recommendation_query.where(
                Recommendation.connection_id == report.connection_id
            )
        recommendation_rows = (
            await session.execute(recommendation_query.order_by(Recommendation.updated_at.desc()))
        ).all()
        columns = [
            "Resource",
            "Type",
            "Region",
            "Action",
            "Status",
            "Monthly savings",
            "Currency",
            "Sources",
        ]
        rows = [
            [
                _cell(resource.name),
                resource.resource_type,
                resource.region,
                recommendation.canonical_action,
                recommendation.status.value,
                str(recommendation.estimated_monthly_savings or ""),
                recommendation.currency or "",
                ", ".join(recommendation.sources),
            ]
            for recommendation, resource in recommendation_rows
        ]
        return "CloudWise Recommendations", columns, rows
    return await _executive_dataset(session, report)


async def _executive_dataset(
    session: AsyncSession, report: GeneratedReport
) -> tuple[str, list[str], list[list[str]]]:
    cost_query = (
        select(CostAggregate.currency, func.sum(CostAggregate.amount))
        .where(
            CostAggregate.organization_id == report.organization_id,
            CostAggregate.granularity == CostGranularity.DAILY,
            CostAggregate.grouping == CostGrouping.SERVICE_REGION,
            CostAggregate.period_start >= report.period_start,
            CostAggregate.period_start <= report.period_end,
        )
        .group_by(CostAggregate.currency)
    )
    savings_query = (
        select(Recommendation.currency, func.sum(Recommendation.estimated_monthly_savings))
        .where(
            Recommendation.organization_id == report.organization_id,
            Recommendation.status.in_(
                (RecommendationStatus.OPEN, RecommendationStatus.ACKNOWLEDGED)
            ),
            Recommendation.currency.is_not(None),
        )
        .group_by(Recommendation.currency)
    )
    if report.connection_id:
        cost_query = cost_query.where(CostAggregate.connection_id == report.connection_id)
        savings_query = savings_query.where(Recommendation.connection_id == report.connection_id)
    costs: dict[str, Decimal] = {}
    for currency, amount in (await session.execute(cost_query)).all():
        costs[currency] = amount or Decimal("0")
    savings: dict[str, Decimal] = {}
    for currency, amount in (await session.execute(savings_query)).all():
        if currency:
            savings[currency] = amount or Decimal("0")
    currencies = sorted(set(costs) | set(savings))
    columns = ["Currency", "Period cost", "Open monthly savings", "Annual opportunity"]
    rows = [
        [
            currency,
            str(costs.get(currency, Decimal("0"))),
            str(savings.get(currency, Decimal("0"))),
            str((savings.get(currency, Decimal("0")) or Decimal("0")) * 12),
        ]
        for currency in currencies
    ]
    return "CloudWise Executive Summary", columns, rows


async def _notify(session: AsyncSession, report: GeneratedReport) -> None:
    if report.schedule_id is None:
        return
    schedule = await session.scalar(
        select(ReportSchedule).where(ReportSchedule.id == report.schedule_id)
    )
    if schedule is None:
        return
    settings = get_settings()
    provider = build_notification_provider(settings)
    for recipient in schedule.recipients:
        status = provider.send(
            recipient,
            f"CloudWise report ready: {schedule.name}",
            "Your scheduled CloudWise report is ready. Sign in to download it before expiration.",
        )
        session.add(
            ReportNotification(
                organization_id=report.organization_id,
                report_id=report.id,
                recipient=recipient,
                status=status,
                provider=provider.name,
                error_code=(
                    "EMAIL_DELIVERY_FAILED" if status is NotificationStatus.FAILED else None
                ),
                created_at=datetime.now(UTC),
            )
        )


async def _dispatch_due_reports() -> None:
    settings = get_settings()
    session_factory = get_session_factory()
    now = datetime.now(UTC)
    report_ids: list[UUID] = []
    async with session_factory() as session:
        schedules = (
            await session.scalars(
                select(ReportSchedule)
                .where(
                    ReportSchedule.enabled.is_(True),
                    ReportSchedule.next_run_at <= now,
                )
                .with_for_update(skip_locked=True)
                .limit(50)
            )
        ).all()
        for schedule in schedules:
            period_start, period_end = _scheduled_period(now.date(), schedule.frequency)
            report = GeneratedReport(
                organization_id=schedule.organization_id,
                requested_by_user_id=schedule.created_by_user_id,
                connection_id=schedule.connection_id,
                schedule_id=schedule.id,
                report_type=schedule.report_type,
                report_format=schedule.report_format,
                status=ReportStatus.QUEUED,
                period_start=period_start,
                period_end=period_end,
                storage_key=None,
                content_type=None,
                byte_size=None,
                checksum_sha256=None,
                error_code=None,
                expires_at=now + timedelta(days=settings.report_retention_days),
                created_at=now,
                started_at=None,
                completed_at=None,
            )
            session.add(report)
            await session.flush()
            report_ids.append(report.id)
            schedule.last_run_at = now
            schedule.next_run_at = next_run(now, schedule.frequency)
            schedule.updated_at = now
        await session.commit()
    for report_id in report_ids:
        celery_app.send_task("cloudwise.reports.generate_report", args=[str(report_id)])


async def _expire_reports() -> None:
    settings = get_settings()
    storage = build_report_storage(settings)
    session_factory = get_session_factory()
    async with session_factory() as session:
        reports = (
            await session.scalars(
                select(GeneratedReport).where(
                    GeneratedReport.status == ReportStatus.COMPLETED,
                    GeneratedReport.expires_at <= datetime.now(UTC),
                )
            )
        ).all()
        for report in reports:
            if report.storage_key:
                try:
                    storage.delete(report.storage_key)
                except ReportStorageError:
                    logger.warning("report_expiration_delete_failed")
                    continue
            report.storage_key = None
            report.status = ReportStatus.EXPIRED
        await session.commit()


async def _mark_failed(report_id: UUID, error_code: str) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        report = await session.scalar(
            select(GeneratedReport).where(GeneratedReport.id == report_id)
        )
        if report:
            report.status = ReportStatus.FAILED
            report.error_code = error_code[:80]
            report.completed_at = datetime.now(UTC)
            await session.commit()


def _scheduled_period(today: date, frequency: ReportFrequency) -> tuple[date, date]:
    end = today - timedelta(days=1)
    if frequency is ReportFrequency.DAILY:
        return end, end
    if frequency is ReportFrequency.WEEKLY:
        return end - timedelta(days=6), end
    previous_month_end = today.replace(day=1) - timedelta(days=1)
    start = previous_month_end.replace(day=1)
    return start, previous_month_end


def _cell(value: str) -> str:
    return f"'{value}" if value.startswith(("=", "+", "-", "@")) else value
