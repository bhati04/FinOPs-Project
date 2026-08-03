"""Authenticated CloudWatch resource metric routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from cloudwise.core.database import get_db_session
from cloudwise.identity.dependencies import CurrentUser
from cloudwise.metrics.schemas import MetricSyncResponse, ResourceMetricResponse
from cloudwise.metrics.service import (
    ActiveMetricSyncError,
    MetricSyncDispatchError,
    MetricSyncService,
)
from cloudwise.organizations.models import OrganizationRole
from cloudwise.worker import celery_app

router = APIRouter()


def get_metric_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MetricSyncService:
    """Build a request-scoped metric service."""
    return MetricSyncService(session, celery_app)


@router.post(
    "/connections/{connection_id}/sync",
    response_model=MetricSyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_metric_sync(
    connection_id: UUID,
    current_user: CurrentUser,
    service: Annotated[MetricSyncService, Depends(get_metric_service)],
    region: str = Query(default="us-east-1", min_length=9, max_length=30),
    days: int = Query(default=14, ge=7, le=30),
) -> MetricSyncResponse:
    """Queue CloudWatch metrics for active resources in one Region."""
    if current_user.role not in {
        OrganizationRole.OWNER,
        OrganizationRole.ADMIN,
        OrganizationRole.ANALYST,
    }:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    try:
        return await service.start_sync(
            current_user.organization_id,
            connection_id,
            region,
            days,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ValueError, ActiveMetricSyncError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except MetricSyncDispatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.get("/syncs", response_model=list[MetricSyncResponse])
async def list_metric_syncs(
    current_user: CurrentUser,
    service: Annotated[MetricSyncService, Depends(get_metric_service)],
) -> list[MetricSyncResponse]:
    """List organization-scoped metric synchronization history."""
    return await service.list_syncs(current_user.organization_id)


@router.get(
    "/resources/{inventory_resource_id}",
    response_model=list[ResourceMetricResponse],
)
async def list_resource_metrics(
    inventory_resource_id: UUID,
    current_user: CurrentUser,
    service: Annotated[MetricSyncService, Depends(get_metric_service)],
    days: int = Query(default=14, ge=1, le=30),
    metric_name: str | None = Query(default=None, min_length=1, max_length=120),
) -> list[ResourceMetricResponse]:
    """List recent CloudWatch datapoints for one tenant-scoped resource."""
    try:
        return await service.list_resource_metrics(
            current_user.organization_id,
            inventory_resource_id,
            days,
            metric_name,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
