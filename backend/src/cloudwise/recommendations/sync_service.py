"""Queue and query organization-scoped AWS recommendation imports."""

from datetime import UTC, datetime
from uuid import UUID

from celery import Celery
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from cloudwise.aws_accounts.models import AWSAccountConnection, ConnectionStatus
from cloudwise.recommendations.models import (
    RecommendationSourceSync,
    RecommendationSyncStatus,
)
from cloudwise.recommendations.schemas import RecommendationSourceSyncResponse


class ActiveRecommendationSyncError(RuntimeError):
    """The connection already has a queued or running import."""


class RecommendationSyncDispatchError(RuntimeError):
    """The persisted import could not be sent to the worker."""


class RecommendationSyncService:
    """Persist, dispatch, and query source synchronization attempts."""

    def __init__(self, session: AsyncSession, celery_app: Celery) -> None:
        self._session = session
        self._celery_app = celery_app

    async def start(
        self,
        organization_id: UUID,
        user_id: UUID,
        connection_id: UUID,
        region: str,
    ) -> RecommendationSourceSyncResponse:
        connection = await self._session.scalar(
            select(AWSAccountConnection).where(
                AWSAccountConnection.id == connection_id,
                AWSAccountConnection.organization_id == organization_id,
            )
        )
        if connection is None:
            raise LookupError("AWS account connection was not found")
        if connection.status is not ConnectionStatus.VERIFIED:
            raise ValueError("AWS account connection must be verified before syncing")
        active = await self._session.scalar(
            select(RecommendationSourceSync.id).where(
                RecommendationSourceSync.connection_id == connection_id,
                RecommendationSourceSync.status.in_(
                    (RecommendationSyncStatus.QUEUED, RecommendationSyncStatus.RUNNING)
                ),
            )
        )
        if active is not None:
            raise ActiveRecommendationSyncError(
                "An AWS recommendation sync is already active for this connection"
            )
        sync = RecommendationSourceSync(
            organization_id=organization_id,
            connection_id=connection_id,
            requested_by_user_id=user_id,
            region=region,
            status=RecommendationSyncStatus.QUEUED,
            imported_count=0,
            matched_resource_count=0,
            unmatched_resource_count=0,
            deduplicated_count=0,
            completed_sources=[],
            failed_sources=[],
            error_code=None,
            created_at=datetime.now(UTC),
            started_at=None,
            completed_at=None,
        )
        self._session.add(sync)
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ActiveRecommendationSyncError(
                "An AWS recommendation sync is already active for this connection"
            ) from exc
        try:
            self._celery_app.send_task(
                "cloudwise.recommendations.sync_aws_recommendations", args=[str(sync.id)]
            )
        except Exception as exc:
            sync.status = RecommendationSyncStatus.FAILED
            sync.error_code = "DISPATCH_FAILED"
            sync.completed_at = datetime.now(UTC)
            await self._session.commit()
            raise RecommendationSyncDispatchError(
                "The recommendation worker could not accept the sync"
            ) from exc
        return self.response(sync)

    async def list(
        self, organization_id: UUID, connection_id: UUID | None
    ) -> list[RecommendationSourceSyncResponse]:
        query = select(RecommendationSourceSync).where(
            RecommendationSourceSync.organization_id == organization_id
        )
        if connection_id is not None:
            query = query.where(RecommendationSourceSync.connection_id == connection_id)
        syncs = (
            await self._session.scalars(query.order_by(RecommendationSourceSync.created_at.desc()))
        ).all()
        return [self.response(sync) for sync in syncs]

    @staticmethod
    def response(sync: RecommendationSourceSync) -> RecommendationSourceSyncResponse:
        return RecommendationSourceSyncResponse(
            id=sync.id,
            connection_id=sync.connection_id,
            region=sync.region,
            status=sync.status,
            imported_count=sync.imported_count,
            matched_resource_count=sync.matched_resource_count,
            unmatched_resource_count=sync.unmatched_resource_count,
            deduplicated_count=sync.deduplicated_count,
            completed_sources=sync.completed_sources,
            failed_sources=sync.failed_sources,
            error_code=sync.error_code,
            created_at=sync.created_at,
            started_at=sync.started_at,
            completed_at=sync.completed_at,
        )
