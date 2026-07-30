"""AWS account and EC2 inventory HTTP routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from cloudwise.aws_accounts.provider import AWSProviderError
from cloudwise.aws_accounts.schemas import (
    AWSIdentityResponse,
    EC2InventoryResponse,
)
from cloudwise.aws_accounts.service import (
    AWSAccountService,
    get_aws_account_service,
)
from cloudwise.identity.dependencies import CurrentUser

router = APIRouter()


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
