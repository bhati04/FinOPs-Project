"""AWS account and EC2 inventory HTTP routes."""

from typing import Annotated

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from cloudwise.aws_accounts.provider import AWSProviderError
from cloudwise.aws_accounts.schemas import (
    AWSIdentityResponse,
    ConnectionCreateRequest,
    ConnectionResponse,
    EC2InventoryResponse,
)
from cloudwise.aws_accounts.service import (
    AWSAccountService,
)
from cloudwise.core.config import get_settings
from cloudwise.core.database import get_db_session
from cloudwise.identity.dependencies import CurrentUser
from cloudwise.organizations.models import OrganizationRole

router = APIRouter()


def get_aws_account_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AWSAccountService:
    return AWSAccountService(session, get_settings())


def require_connection_admin(current_user: CurrentUser) -> None:
    if current_user.role not in {OrganizationRole.OWNER, OrganizationRole.ADMIN}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")


@router.get(
    "/current/identity",
    response_model=AWSIdentityResponse,
    summary="Verify the current AWS account identity",
    responses={503: {"description": "AWS credentials or identity service unavailable"}},
)
def get_current_identity(
    _current_user: CurrentUser,
    service: Annotated[
        AWSAccountService,
        Depends(get_aws_account_service),
    ],
    region: str = Query(
        default="us-east-1",
        min_length=9,
        max_length=30,
        description="AWS Region used by the session",
    ),
) -> AWSIdentityResponse:
    """Return safe identity information for the current AWS role."""

    try:
        return service.get_identity(region=region)

    except AWSProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "AWS_IDENTITY_UNAVAILABLE",
                "message": str(exc),
            },
        ) from exc


@router.get(
    "/current/inventory/ec2",
    response_model=EC2InventoryResponse,
    summary="List EC2 instances in one AWS Region",
    responses={503: {"description": "EC2 inventory could not be retrieved"}},
)
def get_ec2_inventory(
    _current_user: CurrentUser,
    service: Annotated[
        AWSAccountService,
        Depends(get_aws_account_service),
    ],
    region: str = Query(
        default="us-east-1",
        min_length=9,
        max_length=30,
        description="Region from which EC2 instances are collected",
    ),
) -> EC2InventoryResponse:
    """Return normalized EC2 instance inventory."""

    try:
        return service.get_ec2_inventory(region=region)

    except AWSProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "AWS_EC2_INVENTORY_UNAVAILABLE",
                "message": str(exc),
            },
        ) from exc


@router.post(
    "/connections",
    response_model=ConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_connection(
    request: ConnectionCreateRequest,
    current_user: CurrentUser,
    service: Annotated[AWSAccountService, Depends(get_aws_account_service)],
) -> ConnectionResponse:
    """Create a tenant-scoped onboarding draft."""
    require_connection_admin(current_user)
    return await service.create_connection(current_user.organization_id, request)


@router.get("/connections", response_model=list[ConnectionResponse])
async def list_connections(
    current_user: CurrentUser,
    service: Annotated[AWSAccountService, Depends(get_aws_account_service)],
) -> list[ConnectionResponse]:
    """List connections for the authenticated organization."""
    return await service.list_connections(current_user.organization_id)


@router.post("/connections/{connection_id}/verify", response_model=ConnectionResponse)
async def verify_connection(
    connection_id: UUID,
    current_user: CurrentUser,
    service: Annotated[AWSAccountService, Depends(get_aws_account_service)],
    region: str = Query(default="us-east-1", min_length=9, max_length=30),
) -> ConnectionResponse:
    """Verify a pending role using STS AssumeRole."""
    require_connection_admin(current_user)
    try:
        return await service.verify_connection(
            current_user.organization_id,
            connection_id,
            region,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AWSProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "AWS_ROLE_VERIFICATION_FAILED", "message": str(exc)},
        ) from exc
