"""Authenticated deterministic recommendation routes."""

from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from cloudwise.core.config import Settings, get_settings
from cloudwise.core.database import get_db_session
from cloudwise.identity.dependencies import CurrentUser
from cloudwise.organizations.models import OrganizationRole
from cloudwise.recommendations.models import (
    RecommendationSeverity,
    RecommendationStatus,
)
from cloudwise.recommendations.pricing import build_recommendation_pricing_provider
from cloudwise.recommendations.schemas import (
    RecommendationActivityResponse,
    RecommendationCommentCreate,
    RecommendationEvaluationResponse,
    RecommendationResponse,
    RecommendationSourceSyncResponse,
    RecommendationStatusUpdate,
)
from cloudwise.recommendations.service import RecommendationService
from cloudwise.recommendations.sync_service import (
    ActiveRecommendationSyncError,
    RecommendationSyncDispatchError,
    RecommendationSyncService,
)
from cloudwise.worker import celery_app

router = APIRouter()


def get_recommendation_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RecommendationService:
    """Build a request-scoped recommendation service."""
    return RecommendationService(
        session,
        build_recommendation_pricing_provider(settings),
        timedelta(hours=settings.recommendation_pricing_stale_hours),
    )


def require_recommendation_operator(current_user: CurrentUser) -> None:
    """Allow roles permitted to evaluate and review recommendations."""
    if current_user.role not in {
        OrganizationRole.OWNER,
        OrganizationRole.ADMIN,
        OrganizationRole.ANALYST,
    }:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")


def get_recommendation_sync_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RecommendationSyncService:
    """Build a request-scoped AWS recommendation sync service."""
    return RecommendationSyncService(session, celery_app)


@router.post(
    "/evaluate",
    response_model=RecommendationEvaluationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def evaluate_recommendations(
    current_user: CurrentUser,
    service: Annotated[RecommendationService, Depends(get_recommendation_service)],
    connection_id: UUID | None = None,
) -> RecommendationEvaluationResponse:
    """Evaluate deterministic rules against persisted active inventory."""
    require_recommendation_operator(current_user)
    try:
        return await service.evaluate(
            current_user.organization_id,
            current_user.user_id,
            connection_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("", response_model=list[RecommendationResponse])
async def list_recommendations(
    current_user: CurrentUser,
    service: Annotated[RecommendationService, Depends(get_recommendation_service)],
    recommendation_status: Annotated[RecommendationStatus | None, Query(alias="status")] = None,
    severity: RecommendationSeverity | None = None,
    connection_id: UUID | None = None,
) -> list[RecommendationResponse]:
    """List organization-scoped recommendations with safe filters."""
    return await service.list_recommendations(
        current_user.organization_id,
        recommendation_status,
        severity,
        connection_id,
    )


@router.post(
    "/connections/{connection_id}/source-syncs",
    response_model=RecommendationSourceSyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_recommendation_source_sync(
    connection_id: UUID,
    current_user: CurrentUser,
    service: Annotated[RecommendationSyncService, Depends(get_recommendation_sync_service)],
    region: str = Query(default="us-east-1", min_length=9, max_length=30),
) -> RecommendationSourceSyncResponse:
    """Queue read-only Cost Optimization Hub and Compute Optimizer imports."""
    require_recommendation_operator(current_user)
    try:
        return await service.start(
            current_user.organization_id,
            current_user.user_id,
            connection_id,
            region,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ValueError, ActiveRecommendationSyncError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except RecommendationSyncDispatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc


@router.get("/source-syncs", response_model=list[RecommendationSourceSyncResponse])
async def list_recommendation_source_syncs(
    current_user: CurrentUser,
    service: Annotated[RecommendationSyncService, Depends(get_recommendation_sync_service)],
    connection_id: UUID | None = None,
) -> list[RecommendationSourceSyncResponse]:
    """List tenant-scoped AWS recommendation import history."""
    return await service.list(current_user.organization_id, connection_id)


@router.patch("/{recommendation_id}/status", response_model=RecommendationResponse)
async def update_recommendation_status(
    recommendation_id: UUID,
    payload: RecommendationStatusUpdate,
    current_user: CurrentUser,
    service: Annotated[RecommendationService, Depends(get_recommendation_service)],
) -> RecommendationResponse:
    """Apply an authorized recommendation lifecycle transition."""
    require_recommendation_operator(current_user)
    try:
        return await service.update_status(
            current_user.organization_id,
            recommendation_id,
            current_user.user_id,
            payload.status,
            payload.comment,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post(
    "/{recommendation_id}/comments",
    response_model=RecommendationActivityResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_recommendation_comment(
    recommendation_id: UUID,
    payload: RecommendationCommentCreate,
    current_user: CurrentUser,
    service: Annotated[RecommendationService, Depends(get_recommendation_service)],
) -> RecommendationActivityResponse:
    """Append an authorized analyst comment."""
    require_recommendation_operator(current_user)
    try:
        return await service.add_comment(
            current_user.organization_id,
            recommendation_id,
            current_user.user_id,
            payload.comment,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{recommendation_id}/activities",
    response_model=list[RecommendationActivityResponse],
)
async def list_recommendation_activities(
    recommendation_id: UUID,
    current_user: CurrentUser,
    service: Annotated[RecommendationService, Depends(get_recommendation_service)],
) -> list[RecommendationActivityResponse]:
    """List append-only activity visible to the recommendation's organization."""
    try:
        return await service.list_activities(
            current_user.organization_id,
            recommendation_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
