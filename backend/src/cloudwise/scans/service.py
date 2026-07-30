"""Organization-scoped inventory scan application service."""

from datetime import UTC, datetime
from uuid import UUID

from celery import Celery
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from cloudwise.aws_accounts.models import AWSAccountConnection, ConnectionStatus
from cloudwise.scans.models import InventoryResource, InventoryScan, ScanStatus
from cloudwise.scans.schemas import InventoryResourceResponse, InventoryScanResponse


class ActiveScanError(RuntimeError):
    """Raised when a connection already has a queued or running scan."""


class ScanDispatchError(RuntimeError):
    """Raised when a persisted scan cannot be sent to the worker."""


class InventoryScanService:
    """Persist, dispatch, and query tenant-scoped inventory scans."""

    def __init__(self, session: AsyncSession, celery_app: Celery) -> None:
        self._session = session
        self._celery_app = celery_app

    async def start_scan(
        self,
        organization_id: UUID,
        connection_id: UUID,
        region: str,
    ) -> InventoryScanResponse:
        """Queue an EC2 scan for a verified connection."""
        connection = await self._session.scalar(
            select(AWSAccountConnection).where(
                AWSAccountConnection.id == connection_id,
                AWSAccountConnection.organization_id == organization_id,
            )
        )
        if connection is None:
            raise LookupError("AWS account connection was not found")
        if connection.status is not ConnectionStatus.VERIFIED:
            raise ValueError("AWS account connection must be verified before scanning")

        active = await self._session.scalar(
            select(InventoryScan.id).where(
                InventoryScan.connection_id == connection_id,
                InventoryScan.status.in_((ScanStatus.QUEUED, ScanStatus.RUNNING)),
            )
        )
        if active is not None:
            raise ActiveScanError("An inventory scan is already active for this connection")

        scan = InventoryScan(
            organization_id=organization_id,
            connection_id=connection_id,
            region=region,
            status=ScanStatus.QUEUED,
            resource_count=0,
            error_code=None,
            created_at=datetime.now(UTC),
            started_at=None,
            completed_at=None,
        )
        self._session.add(scan)
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ActiveScanError(
                "An inventory scan is already active for this connection"
            ) from exc

        try:
            self._celery_app.send_task(
                "cloudwise.scans.run_inventory_scan",
                args=[str(scan.id)],
            )
        except Exception as exc:
            scan.status = ScanStatus.FAILED
            scan.error_code = "DISPATCH_FAILED"
            scan.completed_at = datetime.now(UTC)
            await self._session.commit()
            raise ScanDispatchError("The inventory worker could not accept the scan") from exc
        return self._scan_response(scan)

    async def list_scans(
        self,
        organization_id: UUID,
        connection_id: UUID | None = None,
    ) -> list[InventoryScanResponse]:
        """List scans visible to one organization."""
        query = select(InventoryScan).where(
            InventoryScan.organization_id == organization_id
        )
        if connection_id is not None:
            query = query.where(InventoryScan.connection_id == connection_id)
        scans = (await self._session.scalars(query.order_by(InventoryScan.created_at.desc()))).all()
        return [self._scan_response(scan) for scan in scans]

    async def list_resources(
        self,
        organization_id: UUID,
        connection_id: UUID | None = None,
        region: str | None = None,
    ) -> list[InventoryResourceResponse]:
        """List the latest persisted resources within a tenant boundary."""
        query = select(InventoryResource).where(
            InventoryResource.organization_id == organization_id
        )
        if connection_id is not None:
            query = query.where(InventoryResource.connection_id == connection_id)
        if region is not None:
            query = query.where(InventoryResource.region == region)
        resources = (
            await self._session.scalars(query.order_by(InventoryResource.name))
        ).all()
        return [self._resource_response(resource) for resource in resources]

    @staticmethod
    def _scan_response(scan: InventoryScan) -> InventoryScanResponse:
        return InventoryScanResponse(
            id=scan.id,
            connection_id=scan.connection_id,
            region=scan.region,
            status=scan.status,
            resource_count=scan.resource_count,
            error_code=scan.error_code,
            created_at=scan.created_at,
            started_at=scan.started_at,
            completed_at=scan.completed_at,
        )

    @staticmethod
    def _resource_response(resource: InventoryResource) -> InventoryResourceResponse:
        return InventoryResourceResponse(
            id=resource.id,
            connection_id=resource.connection_id,
            scan_id=resource.scan_id,
            region=resource.region,
            resource_type=resource.resource_type,
            resource_id=resource.resource_id,
            name=resource.name,
            state=resource.state,
            details=resource.details,
            discovered_at=resource.discovered_at,
        )
