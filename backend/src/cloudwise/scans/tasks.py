"""Celery tasks for read-only customer inventory collection."""

from datetime import UTC, datetime
from uuid import UUID

import structlog
from celery import Task
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from cloudwise.aws_accounts.encryption import ExternalIdCipher
from cloudwise.aws_accounts.models import AWSAccountConnection, ConnectionStatus
from cloudwise.aws_accounts.provider import AWSProvider, AWSProviderError
from cloudwise.core.config import get_settings
from cloudwise.core.database import get_session_factory, run_async_job
from cloudwise.identity import models as identity_models  # noqa: F401
from cloudwise.inventory.provider import AWSInventoryProvider, NormalizedResource
from cloudwise.organizations import models as organization_models  # noqa: F401
from cloudwise.scans.models import InventoryResource, InventoryScan, ScanStatus
from cloudwise.worker import celery_app

logger = structlog.get_logger()


class ScanLockUnavailable(RuntimeError):
    """Signal that another worker currently owns the connection scan lock."""


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="cloudwise.scans.run_inventory_scan",
    max_retries=30,
)
def run_inventory_scan(task: Task, scan_id: str) -> None:
    """Run one scan while holding a per-connection Redis lock."""
    scan_uuid = UUID(scan_id)
    try:
        run_async_job(_run_inventory_scan(scan_uuid))
    except ScanLockUnavailable as exc:
        if task.request.retries >= 30:
            run_async_job(_fail_scan(scan_uuid, "SCAN_LOCK_TIMEOUT"))
            return
        raise task.retry(exc=exc, countdown=30) from exc
    except Exception:
        logger.exception("inventory_scan_task_failed")
        try:
            run_async_job(_fail_scan(scan_uuid, "INVENTORY_WORKER_FAILED"))
        except Exception:
            logger.exception("inventory_scan_failure_status_update_failed")
        raise


async def _run_inventory_scan(scan_id: UUID) -> None:
    settings = get_settings()
    session_factory = get_session_factory()
    async with session_factory() as session:
        scan = await session.scalar(select(InventoryScan).where(InventoryScan.id == scan_id))
        if scan is None or scan.status not in {ScanStatus.QUEUED, ScanStatus.RUNNING}:
            return
        connection_id = scan.connection_id

    redis_client: Redis = Redis.from_url(str(settings.redis_url))
    try:
        lock = redis_client.lock(
            f"cloudwise:scan-lock:{connection_id}",
            timeout=840,
            blocking_timeout=0,
        )
        if not lock.acquire(blocking=False):
            redis_client.close()
            raise ScanLockUnavailable
    except RedisError as exc:
        redis_client.close()
        raise ScanLockUnavailable from exc
    try:
        await _collect_inventory(scan_id)
    finally:
        try:
            lock.release()
        except Exception:
            logger.warning("inventory_scan_lock_release_failed")
        redis_client.close()


async def _collect_inventory(scan_id: UUID) -> None:
    settings = get_settings()
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(InventoryScan, AWSAccountConnection)
            .join(
                AWSAccountConnection,
                AWSAccountConnection.id == InventoryScan.connection_id,
            )
            .where(InventoryScan.id == scan_id)
        )
        row = result.one_or_none()
        if row is None:
            return
        scan, connection = row
        if (
            connection.organization_id != scan.organization_id
            or connection.status is not ConnectionStatus.VERIFIED
        ):
            scan.status = ScanStatus.FAILED
            scan.error_code = "CONNECTION_NOT_VERIFIED"
            scan.completed_at = datetime.now(UTC)
            await session.commit()
            return

        scan.status = ScanStatus.RUNNING
        scan.started_at = datetime.now(UTC)
        await session.commit()

        try:
            cipher = ExternalIdCipher(settings.external_id_encryption_key.get_secret_value())
            provider = AWSProvider.for_assumed_role(
                connection.role_arn,
                cipher.decrypt(connection.encrypted_external_id),
                scan.region,
            )
            collection = AWSInventoryProvider(provider).collect()
            if not collection.completed_resource_types:
                scan.status = ScanStatus.FAILED
                scan.error_code = "AWS_INVENTORY_UNAVAILABLE"
                scan.failed_services = list(collection.failed_services)
                scan.completed_at = datetime.now(UTC)
                await session.commit()
                return
            resources = collection.resources
            discovered_at = datetime.now(UTC)
            for resource_type in collection.completed_resource_types:
                await session.execute(
                    update(InventoryResource)
                    .where(
                        InventoryResource.organization_id == scan.organization_id,
                        InventoryResource.connection_id == scan.connection_id,
                        InventoryResource.region == scan.region,
                        InventoryResource.resource_type == resource_type,
                        InventoryResource.is_active.is_(True),
                    )
                    .values(is_active=False, inactive_at=discovered_at)
                )
            for resource in resources:
                values = _resource_values(scan, resource, discovered_at)
                statement = insert(InventoryResource).values(**values)
                statement = statement.on_conflict_do_update(
                    constraint="uq_inventory_resources_identity",
                    set_={
                        "scan_id": statement.excluded.scan_id,
                        "name": statement.excluded.name,
                        "state": statement.excluded.state,
                        "details": statement.excluded.details,
                        "is_active": True,
                        "last_seen_at": statement.excluded.last_seen_at,
                        "inactive_at": None,
                    },
                )
                await session.execute(statement)
            scan.status = ScanStatus.PARTIAL if collection.failed_services else ScanStatus.COMPLETED
            scan.resource_count = len(resources)
            scan.error_code = "PARTIAL_AWS_ACCESS" if collection.failed_services else None
            scan.failed_services = list(collection.failed_services)
            scan.completed_at = datetime.now(UTC)
            await session.commit()
        except AWSProviderError:
            await session.rollback()
            logger.warning("inventory_scan_aws_request_failed")
            await _fail_scan(scan_id, "AWS_INVENTORY_UNAVAILABLE")
        except Exception:
            await session.rollback()
            logger.exception("inventory_scan_persistence_failed")
            await _fail_scan(scan_id, "INVENTORY_PERSISTENCE_FAILED")


def _resource_values(
    scan: InventoryScan,
    resource: NormalizedResource,
    discovered_at: datetime,
) -> dict[str, object]:
    return {
        "organization_id": scan.organization_id,
        "connection_id": scan.connection_id,
        "scan_id": scan.id,
        "region": resource["region"],
        "resource_type": resource["resource_type"],
        "resource_id": resource["resource_id"],
        "name": resource["name"],
        "state": resource["state"],
        "details": resource["details"],
        "discovered_at": discovered_at,
        "is_active": True,
        "last_seen_at": discovered_at,
        "inactive_at": None,
    }


async def _fail_scan(scan_id: UUID, error_code: str) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        scan = await session.scalar(select(InventoryScan).where(InventoryScan.id == scan_id))
        if scan is None:
            return
        scan.status = ScanStatus.FAILED
        scan.error_code = error_code
        scan.completed_at = datetime.now(UTC)
        await session.commit()
