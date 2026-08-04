"""Celery tasks for read-only AWS recommendation synchronization."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cloudwise.aws_accounts.encryption import ExternalIdCipher
from cloudwise.aws_accounts.models import AWSAccountConnection, ConnectionStatus
from cloudwise.aws_accounts.provider import AWSProvider, AWSProviderError
from cloudwise.core.config import get_settings
from cloudwise.core.database import get_session_factory
from cloudwise.identity import models as identity_models  # noqa: F401
from cloudwise.organizations import models as organization_models  # noqa: F401
from cloudwise.recommendations.external import (
    AWSComputeOptimizerProvider,
    AWSCostOptimizationHubProvider,
    ExternalRecommendation,
    RecommendationProviderError,
)
from cloudwise.recommendations.ingestion import merge_external_recommendations
from cloudwise.recommendations.models import (
    RecommendationSource,
    RecommendationSourceSync,
    RecommendationSyncStatus,
)
from cloudwise.scans import models as scan_models  # noqa: F401
from cloudwise.worker import celery_app

logger = structlog.get_logger()


@celery_app.task(name="cloudwise.recommendations.sync_aws_recommendations")  # type: ignore[untyped-decorator]
def sync_aws_recommendations(sync_id: str) -> None:
    """Run a persisted AWS recommendation sync."""
    asyncio.run(_sync_aws_recommendations(UUID(sync_id)))


async def _sync_aws_recommendations(sync_id: UUID) -> None:
    settings = get_settings()
    session_factory = get_session_factory()
    async with session_factory() as session:
        row = (
            await session.execute(
                select(RecommendationSourceSync, AWSAccountConnection)
                .join(
                    AWSAccountConnection,
                    AWSAccountConnection.id == RecommendationSourceSync.connection_id,
                )
                .where(RecommendationSourceSync.id == sync_id)
            )
        ).one_or_none()
        if row is None:
            return
        sync, connection = row
        if sync.status not in {
            RecommendationSyncStatus.QUEUED,
            RecommendationSyncStatus.RUNNING,
        }:
            return
        if (
            connection.organization_id != sync.organization_id
            or connection.status is not ConnectionStatus.VERIFIED
        ):
            await _fail(sync, session, "CONNECTION_NOT_VERIFIED")
            return
        sync.status = RecommendationSyncStatus.RUNNING
        sync.started_at = datetime.now(UTC)
        await session.commit()

        findings: list[ExternalRecommendation] = []
        completed: set[RecommendationSource] = set()
        failed: list[str] = []
        try:
            cipher = ExternalIdCipher(settings.external_id_encryption_key.get_secret_value())
            provider = AWSProvider.for_assumed_role(
                connection.role_arn,
                cipher.decrypt(connection.encrypted_external_id),
                sync.region,
            )
            try:
                findings.extend(
                    AWSCostOptimizationHubProvider(provider).collect(connection.expected_account_id)
                )
                completed.add(RecommendationSource.COST_OPTIMIZATION_HUB)
            except RecommendationProviderError as exc:
                failed.append(exc.source.value)
            try:
                compute_findings, compute_failures = AWSComputeOptimizerProvider(provider).collect()
                findings.extend(compute_findings)
                failed.extend(compute_failures)
                if not compute_failures:
                    completed.add(RecommendationSource.COMPUTE_OPTIMIZER)
            except RecommendationProviderError as exc:
                failed.append(exc.source.value)

            if not completed and not findings:
                await _fail(
                    sync,
                    session,
                    "AWS_RECOMMENDATION_SOURCES_UNAVAILABLE",
                    failed,
                )
                return
            imported, matched, unmatched, deduplicated = await merge_external_recommendations(
                session, sync, findings, completed
            )
            sync.imported_count = imported
            sync.matched_resource_count = matched
            sync.unmatched_resource_count = unmatched
            sync.deduplicated_count = deduplicated
            sync.completed_sources = sorted(source.value for source in completed)
            sync.failed_sources = sorted(set(failed))
            sync.status = (
                RecommendationSyncStatus.PARTIAL if failed else RecommendationSyncStatus.COMPLETED
            )
            sync.error_code = "PARTIAL_AWS_ACCESS" if failed else None
            sync.completed_at = datetime.now(UTC)
            await session.commit()
        except AWSProviderError:
            await session.rollback()
            logger.warning("recommendation_sync_assume_role_failed")
            await _fail(sync, session, "AWS_ROLE_UNAVAILABLE")
        except Exception:
            await session.rollback()
            logger.exception("recommendation_sync_failed")
            await _fail(sync, session, "RECOMMENDATION_SYNC_FAILED")


async def _fail(
    sync: RecommendationSourceSync,
    session: AsyncSession,
    error_code: str,
    failed_sources: list[str] | None = None,
) -> None:
    sync.status = RecommendationSyncStatus.FAILED
    sync.error_code = error_code
    sync.failed_sources = sorted(set(failed_sources or []))
    sync.completed_at = datetime.now(UTC)
    await session.commit()
