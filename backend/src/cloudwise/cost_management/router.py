"""Authenticated cost management routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from cloudwise.core.database import get_db_session
from cloudwise.cost_management.models import CostGranularity, CostGrouping
from cloudwise.cost_management.schemas import (
    CostAggregateResponse,
    CostForecastResponse,
    CostSyncResponse,
)
from cloudwise.cost_management.service import (
    ActiveCostSyncError,
    CostSyncDispatchError,
    CostSyncService,
)
from cloudwise.identity.dependencies import CurrentUser
from cloudwise.organizations.models import OrganizationRole
from cloudwise.worker import celery_app

router = APIRouter()


def get_cost_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CostSyncService:
    """Build a request-scoped cost service."""
    return CostSyncService(session, celery_app)


@router.post(
    "/connections/{connection_id}/sync",
    response_model=CostSyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_cost_sync(
    connection_id: UUID,
    current_user: CurrentUser,
    service: Annotated[CostSyncService, Depends(get_cost_service)],
) -> CostSyncResponse:
    """Queue Cost Explorer synchronization for a verified connection."""
    if current_user.role not in {
        OrganizationRole.OWNER,
        OrganizationRole.ADMIN,
        OrganizationRole.ANALYST,
    }:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    try:
        return await service.start_sync(current_user.organization_id, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ActiveCostSyncError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except CostSyncDispatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.get("/syncs", response_model=list[CostSyncResponse])
async def list_cost_syncs(
    current_user: CurrentUser,
    service: Annotated[CostSyncService, Depends(get_cost_service)],
) -> list[CostSyncResponse]:
    """List organization-scoped cost synchronization history."""
    return await service.list_syncs(current_user.organization_id)


@router.get("/aggregates", response_model=list[CostAggregateResponse])
async def list_cost_aggregates(
    current_user: CurrentUser,
    service: Annotated[CostSyncService, Depends(get_cost_service)],
    granularity: CostGranularity = Query(default=CostGranularity.DAILY),
    grouping: CostGrouping = Query(default=CostGrouping.SERVICE_REGION),
    connection_id: UUID | None = None,
) -> list[CostAggregateResponse]:
    """List persisted Cost Explorer aggregates."""
    return await service.list_aggregates(
        current_user.organization_id, granularity, grouping, connection_id
    )


@router.get("/forecasts", response_model=list[CostForecastResponse])
async def list_cost_forecasts(
    current_user: CurrentUser,
    service: Annotated[CostSyncService, Depends(get_cost_service)],
    granularity: CostGranularity = Query(default=CostGranularity.DAILY),
    connection_id: UUID | None = None,
) -> list[CostForecastResponse]:
    """List persisted organization-scoped Cost Explorer forecasts."""
    return await service.list_forecasts(
        current_user.organization_id, granularity, connection_id
    )
