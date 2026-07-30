"""Celery tasks for read-only customer inventory collection."""

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from celery import Task
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from cloudwise.aws_accounts.encryption import ExternalIdCipher
from cloudwise.aws_accounts.models import AWSAccountConnection, ConnectionStatus
from cloudwise.aws_accounts.provider import AWSProvider, AWSProviderError
from cloudwise.core.config import get_settings
from cloudwise.core.database import get_session_factory
from cloudwise.scans.models import InventoryResource, InventoryScan, ScanStatus
from cloudwise.worker import celery_app

logger = structlog.get_logger()


class ScanLockUnavailable(RuntimeError):
    """Signal that another worker currently owns the connection scan lock."""


@celery_app.task(
    bind=True,
    name="cloudwise.scans.run_inventory_scan",
    max_retries=30,
)
def run_inventory_scan(task: Task, scan_id: str) -> None:
    """Run one scan while holding a per-connection Redis lock."""
    try:
        asyncio.run(_run_inventory_scan(UUID(scan_id)))
    except ScanLockUnavailable as exc:
        if task.request.retries >= 30:
            asyncio.run(_fail_scan(UUID(scan_id), "SCAN_LOCK_TIMEOUT"))
            return
        raise task.retry(exc=exc, countdown=30) from exc


async def _run_inventory_scan(scan_id: UUID) -> None:
    settings = get_settings()
    session_factory = get_session_factory()
    async with session_factory() as session:
        scan = await session.scalar(select(InventoryScan).where(InventoryScan.id == scan_id))
        if scan is None or scan.status not in {ScanStatus.QUEUED, ScanStatus.RUNNING}:
            return
        connection_id = scan.connection_id

    redis_client: Redis[bytes] = Redis.from_url(str(settings.redis_url))
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
            cipher = ExternalIdCipher(
                settings.external_id_encryption_key.get_secret_value()
            )
            provider = AWSProvider.for_assumed_role(
                connection.role_arn,
                cipher.decrypt(connection.encrypted_external_id),
                scan.region,
            )
            resources = provider.list_ec2_instances()
            discovered_at = datetime.now(UTC)
            discovered_ids = [resource["resource_id"] for resource in resources]
            stale_resources = delete(InventoryResource).where(
                InventoryResource.organization_id == scan.organization_id,
                InventoryResource.connection_id == scan.connection_id,
                InventoryResource.region == scan.region,
                InventoryResource.resource_type == "ec2_instance",
            )
            if discovered_ids:
                stale_resources = stale_resources.where(
                    InventoryResource.resource_id.not_in(discovered_ids)
                )
            await session.execute(stale_resources)
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
                        "discovered_at": statement.excluded.discovered_at,
                    },
                )
                await session.execute(statement)
            scan.status = ScanStatus.COMPLETED
            scan.resource_count = len(resources)
            scan.error_code = None
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
    resource: dict[str, Any],
    discovered_at: datetime,
) -> dict[str, object]:
    details = {
        "instance_type": resource["instance_type"],
        "availability_zone": resource["availability_zone"],
        "private_ip": resource.get("private_ip"),
        "public_ip": resource.get("public_ip"),
        "launch_time": resource["launch_time"].isoformat(),
        "tags": resource["tags"],
    }
    return {
        "organization_id": scan.organization_id,
        "connection_id": scan.connection_id,
        "scan_id": scan.id,
        "region": scan.region,
        "resource_type": "ec2_instance",
        "resource_id": resource["resource_id"],
        "name": resource["name"],
        "state": resource["state"],
        "details": details,
        "discovered_at": discovered_at,
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
