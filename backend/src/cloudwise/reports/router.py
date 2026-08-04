"""Authenticated report, schedule, download, and audit routes."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from cloudwise.core.config import Settings, get_settings
from cloudwise.core.database import get_db_session
from cloudwise.identity.dependencies import CurrentUser
from cloudwise.organizations.models import OrganizationRole
from cloudwise.reports.models import ReportStatus
from cloudwise.reports.schemas import (
    AuditEventResponse,
    ReportCreate,
    ReportResponse,
    ReportScheduleCreate,
    ReportScheduleResponse,
    ReportScheduleUpdate,
)
from cloudwise.reports.service import ReportDispatchError, ReportService
from cloudwise.reports.storage import ReportStorageError, build_report_storage
from cloudwise.worker import celery_app

router = APIRouter()


def get_report_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReportService:
    """Build a request-scoped report service."""
    return ReportService(session, celery_app, settings)


def require_report_operator(current_user: CurrentUser) -> None:
    if current_user.role not in {
        OrganizationRole.OWNER,
        OrganizationRole.ADMIN,
        OrganizationRole.ANALYST,
    }:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")


def require_audit_reader(current_user: CurrentUser) -> None:
    if current_user.role not in {OrganizationRole.OWNER, OrganizationRole.ADMIN}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")


@router.post("", response_model=ReportResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_report(
    payload: ReportCreate,
    current_user: CurrentUser,
    service: Annotated[ReportService, Depends(get_report_service)],
) -> ReportResponse:
    """Queue a tenant-scoped CSV or PDF report."""
    require_report_operator(current_user)
    try:
        return await service.create_report(
            current_user.organization_id, current_user.user_id, payload
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ReportDispatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc


@router.get("", response_model=list[ReportResponse])
async def list_reports(
    current_user: CurrentUser,
    service: Annotated[ReportService, Depends(get_report_service)],
) -> list[ReportResponse]:
    """List generated report metadata for the current organization."""
    return await service.list_reports(current_user.organization_id)


@router.post(
    "/schedules",
    response_model=ReportScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_report_schedule(
    payload: ReportScheduleCreate,
    current_user: CurrentUser,
    service: Annotated[ReportService, Depends(get_report_service)],
) -> ReportScheduleResponse:
    """Create a database-driven recurring report schedule."""
    require_report_operator(current_user)
    try:
        return await service.create_schedule(
            current_user.organization_id, current_user.user_id, payload
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/schedules", response_model=list[ReportScheduleResponse])
async def list_report_schedules(
    current_user: CurrentUser,
    service: Annotated[ReportService, Depends(get_report_service)],
) -> list[ReportScheduleResponse]:
    """List organization-scoped report schedules."""
    return await service.list_schedules(current_user.organization_id)


@router.patch("/schedules/{schedule_id}", response_model=ReportScheduleResponse)
async def update_report_schedule(
    schedule_id: UUID,
    payload: ReportScheduleUpdate,
    current_user: CurrentUser,
    service: Annotated[ReportService, Depends(get_report_service)],
) -> ReportScheduleResponse:
    """Enable or disable one organization-scoped schedule."""
    require_report_operator(current_user)
    try:
        return await service.set_schedule_enabled(
            current_user.organization_id, schedule_id, payload.enabled
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEventResponse])
async def list_audit_events(
    current_user: CurrentUser,
    service: Annotated[ReportService, Depends(get_report_service)],
    limit: int = Query(default=100, ge=1, le=500),
    action: str | None = Query(default=None, max_length=120),
) -> list[AuditEventResponse]:
    """List immutable mutation history for organization administrators."""
    require_audit_reader(current_user)
    return await service.list_audit_events(current_user.organization_id, limit, action)


@router.get("/{report_id}/download")
async def download_report(
    report_id: UUID,
    current_user: CurrentUser,
    service: Annotated[ReportService, Depends(get_report_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Stream a private report only to a member of its organization."""
    report = await service.get_report(current_user.organization_id, report_id)
    if report.status is ReportStatus.EXPIRED or report.expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Report has expired")
    if report.status is not ReportStatus.COMPLETED or not report.storage_key:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Report is not ready")
    try:
        content = build_report_storage(settings).get(report.storage_key)
    except ReportStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Report storage is temporarily unavailable",
        ) from exc
    extension = report.report_format.value
    filename = f"cloudwise-{report.report_type.value}-{report.id}.{extension}"
    return Response(
        content=content,
        media_type=report.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
