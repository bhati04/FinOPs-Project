"""Organization-scoped CloudWatch metric synchronization service."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from celery import Celery
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from cloudwise.aws_accounts.models import AWSAccountConnection, ConnectionStatus
from cloudwise.metrics.models import MetricSync, MetricSyncStatus, ResourceMetric
from cloudwise.metrics.schemas import MetricSyncResponse, ResourceMetricResponse
from cloudwise.scans.models import InventoryResource


class ActiveMetricSyncError(RuntimeError):
    """Raised when a connection and Region already have active metric work."""


class MetricSyncDispatchError(RuntimeError):
    """Raised when a persisted metric sync cannot be sent to the worker."""


class MetricSyncService:
    """Dispatch and query tenant-scoped CloudWatch metrics."""

    def __init__(self, session: AsyncSession, celery_app: Celery) -> None:
        self._session = session
        self._celery_app = celery_app

    async def start_sync(
        self,
        organization_id: UUID,
        connection_id: UUID,
        region: str,
        days: int,
    ) -> MetricSyncResponse:
        """Queue a bounded CloudWatch synchronization for verified inventory."""
        connection = await self._session.scalar(
            select(AWSAccountConnection).where(
                AWSAccountConnection.id == connection_id,
                AWSAccountConnection.organization_id == organization_id,
            )
        )
        if connection is None:
            raise LookupError("AWS account connection was not found")
        if connection.status is not ConnectionStatus.VERIFIED:
            raise ValueError("AWS account connection must be verified")
        active = await self._session.scalar(
            select(MetricSync.id).where(
                MetricSync.organization_id == organization_id,
                MetricSync.connection_id == connection_id,
                MetricSync.region == region,
                MetricSync.status.in_((MetricSyncStatus.QUEUED, MetricSyncStatus.RUNNING)),
            )
        )
        if active is not None:
            raise ActiveMetricSyncError("A metric synchronization is already active")
        created_at = datetime.now(UTC)
        window_end = created_at.replace(minute=0, second=0, microsecond=0)
        sync = MetricSync(
            organization_id=organization_id,
            connection_id=connection_id,
            region=region,
            status=MetricSyncStatus.QUEUED,
            window_start=window_end - timedelta(days=days),
            window_end=window_end,
            record_count=0,
            failed_batch_count=0,
            error_code=None,
            created_at=created_at,
            started_at=None,
            completed_at=None,
        )
        self._session.add(sync)
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ActiveMetricSyncError("A metric synchronization is already active") from exc
        try:
            self._celery_app.send_task("cloudwise.metrics.synchronize", args=[str(sync.id)])
        except Exception as exc:
            sync.status = MetricSyncStatus.FAILED
            sync.error_code = "DISPATCH_FAILED"
            sync.completed_at = datetime.now(UTC)
            await self._session.commit()
            raise MetricSyncDispatchError(
                "The metric synchronization worker could not accept the request"
            ) from exc
        return self._sync_response(sync)

    async def list_syncs(self, organization_id: UUID) -> list[MetricSyncResponse]:
        """List metric synchronization history within one organization."""
        syncs = (
            await self._session.scalars(
                select(MetricSync)
                .where(MetricSync.organization_id == organization_id)
                .order_by(MetricSync.created_at.desc())
            )
        ).all()
        return [self._sync_response(sync) for sync in syncs]

    async def list_resource_metrics(
        self,
        organization_id: UUID,
        inventory_resource_id: UUID,
        days: int,
        metric_name: str | None,
    ) -> list[ResourceMetricResponse]:
        """Return recent datapoints for one organization-scoped inventory resource."""
        resource = await self._session.scalar(
            select(InventoryResource).where(
                InventoryResource.id == inventory_resource_id,
                InventoryResource.organization_id == organization_id,
            )
        )
        if resource is None:
            raise LookupError("Inventory resource was not found")
        start = datetime.now(UTC) - timedelta(days=days)
        query = select(ResourceMetric).where(
            ResourceMetric.organization_id == organization_id,
            ResourceMetric.inventory_resource_id == inventory_resource_id,
            ResourceMetric.timestamp >= start,
        )
        if metric_name is not None:
            query = query.where(ResourceMetric.metric_name == metric_name)
        points = (
            await self._session.scalars(
                query.order_by(ResourceMetric.timestamp, ResourceMetric.metric_name)
            )
        ).all()
        return [
            ResourceMetricResponse(
                inventory_resource_id=resource.id,
                resource_type=resource.resource_type,
                resource_name=resource.name,
                region=resource.region,
                namespace=point.namespace,
                metric_name=point.metric_name,
                statistic=point.statistic,
                unit=point.unit,
                timestamp=point.timestamp,
                value=point.value,
            )
            for point in points
        ]

    @staticmethod
    def _sync_response(sync: MetricSync) -> MetricSyncResponse:
        return MetricSyncResponse(
            id=sync.id,
            connection_id=sync.connection_id,
            region=sync.region,
            status=sync.status,
            window_start=sync.window_start,
            window_end=sync.window_end,
            record_count=sync.record_count,
            failed_batch_count=sync.failed_batch_count,
            error_code=sync.error_code,
            created_at=sync.created_at,
            started_at=sync.started_at,
            completed_at=sync.completed_at,
        )
