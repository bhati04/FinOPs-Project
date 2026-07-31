"""Authenticated inventory scan HTTP routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from cloudwise.core.database import get_db_session
from cloudwise.identity.dependencies import CurrentUser
from cloudwise.organizations.models import OrganizationRole
from cloudwise.scans.schemas import InventoryResourceResponse, InventoryScanResponse
from cloudwise.scans.service import (
    ActiveScanError,
    InventoryScanService,
    ScanDispatchError,
)
from cloudwise.worker import celery_app

router = APIRouter()


def get_scan_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InventoryScanService:
    """Build a request-scoped scan service."""
    return InventoryScanService(session, celery_app)


def require_scan_operator(current_user: CurrentUser) -> None:
    """Allow roles that are permitted to invoke customer AWS reads."""
    if current_user.role not in {
        OrganizationRole.OWNER,
        OrganizationRole.ADMIN,
        OrganizationRole.ANALYST,
    }:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")


@router.post(
    "/aws-accounts/connections/{connection_id}/scans",
    response_model=InventoryScanResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_inventory_scan(
    connection_id: UUID,
    current_user: CurrentUser,
    service: Annotated[InventoryScanService, Depends(get_scan_service)],
    region: str = Query(default="us-east-1", min_length=9, max_length=30),
) -> InventoryScanResponse:
    """Queue a read-only EC2 inventory scan."""
    require_scan_operator(current_user)
    try:
        return await service.start_scan(
            current_user.organization_id,
            connection_id,
            region,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ActiveScanError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ScanDispatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.get("/scans", response_model=list[InventoryScanResponse])
async def list_inventory_scans(
    current_user: CurrentUser,
    service: Annotated[InventoryScanService, Depends(get_scan_service)],
    connection_id: UUID | None = None,
) -> list[InventoryScanResponse]:
    """List scan history for the authenticated organization."""
    return await service.list_scans(current_user.organization_id, connection_id)


@router.get("/inventory/resources", response_model=list[InventoryResourceResponse])
async def list_inventory_resources(
    current_user: CurrentUser,
    service: Annotated[InventoryScanService, Depends(get_scan_service)],
    connection_id: UUID | None = None,
    region: str | None = Query(default=None, min_length=9, max_length=30),
    include_inactive: bool = False,
) -> list[InventoryResourceResponse]:
    """List persisted resources for the authenticated organization."""
    return await service.list_resources(
        current_user.organization_id,
        connection_id,
        region,
        include_inactive,
    )
