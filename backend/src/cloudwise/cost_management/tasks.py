"""Celery Cost Explorer synchronization tasks."""

import asyncio
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from cloudwise.aws_accounts.encryption import ExternalIdCipher
from cloudwise.aws_accounts.models import AWSAccountConnection, ConnectionStatus
from cloudwise.aws_accounts.provider import AWSProvider, AWSProviderError
from cloudwise.core.config import get_settings
from cloudwise.core.database import get_session_factory
from cloudwise.cost_management.models import (
    CostAggregate,
    CostForecast,
    CostGranularity,
    CostGrouping,
    CostSync,
    CostSyncStatus,
)
from cloudwise.cost_management.provider import (
    AWSCostProvider,
    CostForecastRecord,
    CostProviderError,
    CostRecord,
)
from cloudwise.identity import models as identity_models  # noqa: F401
from cloudwise.organizations import models as organization_models  # noqa: F401
from cloudwise.worker import celery_app

logger = structlog.get_logger()


def _forecast_windows(
    today: date,
) -> tuple[tuple[CostGranularity, date, date], ...]:
    """Build valid Cost Explorer horizons whose inclusive start is not future."""
    return (
        (CostGranularity.DAILY, today, today + timedelta(days=30)),
        (CostGranularity.MONTHLY, today, today + timedelta(days=90)),
    )


@celery_app.task(name="cloudwise.costs.synchronize")
def synchronize_costs(sync_id: str) -> None:
    """Synchronize daily and monthly Cost Explorer aggregates."""
    asyncio.run(_synchronize_costs(UUID(sync_id)))


async def _synchronize_costs(sync_id: UUID) -> None:
    settings = get_settings()
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(CostSync, AWSAccountConnection)
            .join(AWSAccountConnection, AWSAccountConnection.id == CostSync.connection_id)
            .where(CostSync.id == sync_id)
            .with_for_update(of=CostSync)
        )
        row = result.one_or_none()
        if row is None:
            return
        sync, connection = row
        if sync.status is not CostSyncStatus.QUEUED:
            return
        if (
            connection.status is not ConnectionStatus.VERIFIED
            or connection.organization_id != sync.organization_id
        ):
            sync.status = CostSyncStatus.FAILED
            sync.error_code = "CONNECTION_NOT_VERIFIED"
            sync.completed_at = datetime.now(UTC)
            await session.commit()
            return
        sync.status = CostSyncStatus.RUNNING
        sync.started_at = datetime.now(UTC)
        await session.commit()
        failed_facets: list[str] = []
        try:
            provider = AWSProvider.for_assumed_role(
                connection.role_arn,
                ExternalIdCipher(
                    settings.external_id_encryption_key.get_secret_value()
                ).decrypt(connection.encrypted_external_id),
                "us-east-1",
            )
            cost_provider = AWSCostProvider(provider)
            today = datetime.now(UTC).date()
            daily_start = today - timedelta(days=30)
            monthly_start = date(today.year - 1, today.month, 1)
            groupings = [CostGrouping.SERVICE_REGION, CostGrouping.USAGE_TYPE]
            if settings.cost_allocation_tag_key:
                groupings.append(CostGrouping.TAG)
            records: list[CostRecord] = []
            windows = (
                (CostGranularity.DAILY, daily_start),
                (CostGranularity.MONTHLY, monthly_start),
            )
            for granularity, start in windows:
                for grouping in groupings:
                    facet = f"{granularity.value}:{grouping.value}"
                    try:
                        records.extend(
                            cost_provider.get_costs(
                                start,
                                today,
                                granularity,
                                grouping,
                                tag_key=settings.cost_allocation_tag_key,
                            )
                        )
                    except CostProviderError:
                        failed_facets.append(facet)
                        logger.warning(
                            "cost_explorer_facet_failed",
                            granularity=granularity.value,
                            grouping=grouping.value,
                        )
            forecasts: list[CostForecastRecord] = []
            for granularity, start, end in _forecast_windows(today):
                try:
                    forecasts.extend(
                        cost_provider.get_forecast(
                            start,
                            end,
                            granularity,
                        )
                    )
                except CostProviderError:
                    failed_facets.append(f"{granularity.value}:forecast")
                    logger.warning(
                        "cost_explorer_forecast_failed",
                        granularity=granularity.value,
                    )
            if not records:
                raise CostProviderError("No Cost Explorer aggregates were available")
            updated_at = datetime.now(UTC)
            for record in records:
                statement = insert(CostAggregate).values(
                    organization_id=sync.organization_id,
                    connection_id=sync.connection_id,
                    sync_id=sync.id,
                    updated_at=updated_at,
                    **record,
                )
                await session.execute(
                    statement.on_conflict_do_update(
                        constraint="uq_cost_aggregates_dimensions",
                        set_={
                            "sync_id": statement.excluded.sync_id,
                            "amount": statement.excluded.amount,
                            "updated_at": statement.excluded.updated_at,
                        },
                    )
                )
            for forecast in forecasts:
                statement = insert(CostForecast).values(
                    organization_id=sync.organization_id,
                    connection_id=sync.connection_id,
                    sync_id=sync.id,
                    updated_at=updated_at,
                    **forecast,
                )
                await session.execute(
                    statement.on_conflict_do_update(
                        constraint="uq_cost_forecasts_period",
                        set_={
                            "sync_id": statement.excluded.sync_id,
                            "mean_amount": statement.excluded.mean_amount,
                            "lower_bound": statement.excluded.lower_bound,
                            "upper_bound": statement.excluded.upper_bound,
                            "updated_at": statement.excluded.updated_at,
                        },
                    )
                )
            sync.status = (
                CostSyncStatus.PARTIAL if failed_facets else CostSyncStatus.COMPLETED
            )
            sync.record_count = len(records) + len(forecasts)
            sync.error_code = "COST_DATA_PARTIAL" if failed_facets else None
            sync.failed_facets = failed_facets
            sync.completed_at = updated_at
            await session.commit()
        except AWSProviderError:
            await session.rollback()
            logger.warning("cost_customer_role_unavailable")
            await _fail_sync(sync_id, "AWS_ROLE_UNAVAILABLE")
        except CostProviderError:
            await session.rollback()
            logger.warning("cost_explorer_synchronization_failed")
            await _fail_sync(
                sync_id,
                "COST_EXPLORER_UNAVAILABLE",
                failed_facets,
            )
        except Exception:
            await session.rollback()
            logger.exception("cost_synchronization_persistence_failed")
            await _fail_sync(sync_id, "COST_PERSISTENCE_FAILED")


async def _fail_sync(
    sync_id: UUID,
    error_code: str,
    failed_facets: list[str] | None = None,
) -> None:
    async with get_session_factory()() as session:
        sync = await session.scalar(select(CostSync).where(CostSync.id == sync_id))
        if sync is None:
            return
        sync.status = CostSyncStatus.FAILED
        sync.error_code = error_code
        sync.failed_facets = failed_facets or []
        sync.completed_at = datetime.now(UTC)
        await session.commit()
