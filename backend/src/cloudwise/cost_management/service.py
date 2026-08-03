"""Organization-scoped cost synchronization service."""

from datetime import UTC, datetime
from uuid import UUID

from celery import Celery
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from cloudwise.aws_accounts.models import AWSAccountConnection, ConnectionStatus
from cloudwise.cost_management.models import (
    CostAggregate,
    CostForecast,
    CostGranularity,
    CostGrouping,
    CostSync,
    CostSyncStatus,
)
from cloudwise.cost_management.schemas import (
    CostAggregateResponse,
    CostForecastResponse,
    CostSyncResponse,
)


class ActiveCostSyncError(RuntimeError):
    """Raised when a connection already has queued or running cost work."""


class CostSyncDispatchError(RuntimeError):
    """Raised when a persisted cost sync cannot be sent to the worker."""


class CostSyncService:
    """Dispatch and query tenant-scoped Cost Explorer data."""

    def __init__(self, session: AsyncSession, celery_app: Celery) -> None:
        self._session = session
        self._celery_app = celery_app

    async def start_sync(
        self, organization_id: UUID, connection_id: UUID
    ) -> CostSyncResponse:
        """Queue a cost synchronization for a verified connection."""
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
            select(CostSync.id).where(
                CostSync.organization_id == organization_id,
                CostSync.connection_id == connection_id,
                CostSync.status.in_((CostSyncStatus.QUEUED, CostSyncStatus.RUNNING)),
            )
        )
        if active is not None:
            raise ActiveCostSyncError("A cost synchronization is already active")
        sync = CostSync(
            organization_id=organization_id,
            connection_id=connection_id,
            status=CostSyncStatus.QUEUED,
            record_count=0,
            error_code=None,
            failed_facets=[],
            created_at=datetime.now(UTC),
            started_at=None,
            completed_at=None,
        )
        self._session.add(sync)
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ActiveCostSyncError("A cost synchronization is already active") from exc
        try:
            self._celery_app.send_task("cloudwise.costs.synchronize", args=[str(sync.id)])
        except Exception as exc:
            sync.status = CostSyncStatus.FAILED
            sync.error_code = "DISPATCH_FAILED"
            sync.completed_at = datetime.now(UTC)
            await self._session.commit()
            raise CostSyncDispatchError(
                "The cost synchronization worker could not accept the request"
            ) from exc
        return self._sync_response(sync)

    async def list_syncs(self, organization_id: UUID) -> list[CostSyncResponse]:
        """List cost synchronization history inside a tenant boundary."""
        syncs = (
            await self._session.scalars(
                select(CostSync)
                .where(CostSync.organization_id == organization_id)
                .order_by(CostSync.created_at.desc())
            )
        ).all()
        return [self._sync_response(sync) for sync in syncs]

    async def list_aggregates(
        self,
        organization_id: UUID,
        granularity: CostGranularity,
        grouping: CostGrouping,
        connection_id: UUID | None,
    ) -> list[CostAggregateResponse]:
        """Return persisted aggregates without mixing organizations."""
        query = select(CostAggregate).where(
            CostAggregate.organization_id == organization_id,
            CostAggregate.granularity == granularity,
            CostAggregate.grouping == grouping,
        )
        if connection_id is not None:
            query = query.where(CostAggregate.connection_id == connection_id)
        rows = (
            await self._session.scalars(
                query.order_by(CostAggregate.period_start, CostAggregate.service)
            )
        ).all()
        return [
            CostAggregateResponse(
                connection_id=row.connection_id,
                period_start=row.period_start,
                granularity=row.granularity,
                grouping=row.grouping,
                service=row.service,
                region=row.region,
                usage_type=row.usage_type,
                tag_key=row.tag_key,
                tag_value=row.tag_value,
                amount=row.amount,
                currency=row.currency,
            )
            for row in rows
        ]

    async def list_forecasts(
        self,
        organization_id: UUID,
        granularity: CostGranularity,
        connection_id: UUID | None,
    ) -> list[CostForecastResponse]:
        """Return persisted forecasts without crossing tenant boundaries."""
        query = select(CostForecast).where(
            CostForecast.organization_id == organization_id,
            CostForecast.granularity == granularity,
        )
        if connection_id is not None:
            query = query.where(CostForecast.connection_id == connection_id)
        rows = (
            await self._session.scalars(
                query.order_by(CostForecast.period_start, CostForecast.connection_id)
            )
        ).all()
        return [
            CostForecastResponse(
                connection_id=row.connection_id,
                period_start=row.period_start,
                period_end=row.period_end,
                granularity=row.granularity,
                mean_amount=row.mean_amount,
                lower_bound=row.lower_bound,
                upper_bound=row.upper_bound,
                currency=row.currency,
            )
            for row in rows
        ]

    @staticmethod
    def _sync_response(sync: CostSync) -> CostSyncResponse:
        return CostSyncResponse(
            id=sync.id,
            connection_id=sync.connection_id,
            status=sync.status,
            record_count=sync.record_count,
            error_code=sync.error_code,
            failed_facets=sync.failed_facets,
            created_at=sync.created_at,
            started_at=sync.started_at,
            completed_at=sync.completed_at,
        )
