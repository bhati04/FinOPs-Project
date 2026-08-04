"""Celery CloudWatch resource metric synchronization tasks."""

from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from cloudwise.aws_accounts.encryption import ExternalIdCipher
from cloudwise.aws_accounts.models import AWSAccountConnection, ConnectionStatus
from cloudwise.aws_accounts.provider import AWSProvider, AWSProviderError
from cloudwise.core.config import get_settings
from cloudwise.core.database import get_session_factory, run_async_job
from cloudwise.identity import models as identity_models  # noqa: F401
from cloudwise.metrics.models import MetricSync, MetricSyncStatus, ResourceMetric
from cloudwise.metrics.provider import RESOURCE_METRICS, AWSMetricProvider, MetricResource
from cloudwise.organizations import models as organization_models  # noqa: F401
from cloudwise.scans.models import InventoryResource
from cloudwise.worker import celery_app

logger = structlog.get_logger()


@celery_app.task(name="cloudwise.metrics.synchronize")  # type: ignore[untyped-decorator]
def synchronize_metrics(sync_id: str) -> None:
    """Synchronize bounded CloudWatch history for active inventory resources."""
    run_async_job(_synchronize_metrics(UUID(sync_id)))


async def _synchronize_metrics(sync_id: UUID) -> None:
    settings = get_settings()
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(MetricSync, AWSAccountConnection)
            .join(AWSAccountConnection, AWSAccountConnection.id == MetricSync.connection_id)
            .where(MetricSync.id == sync_id)
            .with_for_update(of=MetricSync)
        )
        row = result.one_or_none()
        if row is None:
            return
        sync, connection = row
        if sync.status is not MetricSyncStatus.QUEUED:
            return
        if (
            connection.status is not ConnectionStatus.VERIFIED
            or connection.organization_id != sync.organization_id
        ):
            sync.status = MetricSyncStatus.FAILED
            sync.error_code = "CONNECTION_NOT_VERIFIED"
            sync.completed_at = datetime.now(UTC)
            await session.commit()
            return
        sync.status = MetricSyncStatus.RUNNING
        sync.started_at = datetime.now(UTC)
        await session.commit()

        try:
            resources = (
                await session.scalars(
                    select(InventoryResource).where(
                        InventoryResource.organization_id == sync.organization_id,
                        InventoryResource.connection_id == sync.connection_id,
                        InventoryResource.region == sync.region,
                        InventoryResource.is_active.is_(True),
                        InventoryResource.resource_type.in_(tuple(RESOURCE_METRICS)),
                    )
                )
            ).all()
            metric_resources = [
                MetricResource(
                    id=resource.id,
                    resource_type=resource.resource_type,
                    resource_id=resource.resource_id,
                    name=resource.name,
                )
                for resource in resources
                if resource.resource_type != "load_balancer"
                or resource.details.get("type") == "application"
            ]
            provider = AWSProvider.for_assumed_role(
                connection.role_arn,
                ExternalIdCipher(settings.external_id_encryption_key.get_secret_value()).decrypt(
                    connection.encrypted_external_id
                ),
                sync.region,
            )
            collection = await asyncio.to_thread(
                AWSMetricProvider(provider).get_metrics,
                metric_resources,
                sync.window_start,
                sync.window_end,
            )
            batch_count = (collection.query_count + 499) // 500
            if (
                batch_count
                and collection.failed_batch_count == batch_count
                and not collection.records
            ):
                sync.status = MetricSyncStatus.FAILED
                sync.error_code = "CLOUDWATCH_METRICS_UNAVAILABLE"
                sync.failed_batch_count = collection.failed_batch_count
                sync.completed_at = datetime.now(UTC)
                await session.commit()
                return
            updated_at = datetime.now(UTC)
            for record in collection.records:
                statement = insert(ResourceMetric).values(
                    organization_id=sync.organization_id,
                    connection_id=sync.connection_id,
                    sync_id=sync.id,
                    updated_at=updated_at,
                    **record,
                )
                await session.execute(
                    statement.on_conflict_do_update(
                        constraint="uq_resource_metrics_datapoint",
                        set_={
                            "sync_id": statement.excluded.sync_id,
                            "value": statement.excluded.value,
                            "unit": statement.excluded.unit,
                            "updated_at": statement.excluded.updated_at,
                        },
                    )
                )
            sync.status = (
                MetricSyncStatus.PARTIAL
                if collection.failed_batch_count
                else MetricSyncStatus.COMPLETED
            )
            sync.record_count = len(collection.records)
            sync.failed_batch_count = collection.failed_batch_count
            sync.error_code = "CLOUDWATCH_DATA_PARTIAL" if collection.failed_batch_count else None
            sync.completed_at = updated_at
            await session.commit()
        except AWSProviderError:
            await session.rollback()
            logger.warning("metric_customer_role_unavailable")
            await _fail_sync(sync_id, "AWS_ROLE_UNAVAILABLE")
        except Exception:
            await session.rollback()
            logger.exception("metric_synchronization_persistence_failed")
            await _fail_sync(sync_id, "METRIC_PERSISTENCE_FAILED")


async def _fail_sync(sync_id: UUID, error_code: str) -> None:
    async with get_session_factory()() as session:
        sync = await session.scalar(select(MetricSync).where(MetricSync.id == sync_id))
        if sync is None:
            return
        sync.status = MetricSyncStatus.FAILED
        sync.error_code = error_code
        sync.completed_at = datetime.now(UTC)
        await session.commit()
