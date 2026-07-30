"""Public response schemas for AWS account endpoints."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from cloudwise.aws_accounts.models import ConnectionStatus


class AWSIdentityResponse(BaseModel):
    """Verified AWS account identity."""

    account_id: str = Field(pattern=r"^\d{12}$")
    principal_arn: str
    principal_id: str
    authentication_type: str
    region: str
    status: str


class EC2ResourceResponse(BaseModel):
    """Normalized EC2 instance returned by the inventory endpoint."""

    resource_id: str
    name: str
    instance_type: str
    state: str
    availability_zone: str
    private_ip: str | None = None
    public_ip: str | None = None
    launch_time: datetime
    tags: dict[str, Any]


class EC2InventoryResponse(BaseModel):
    """EC2 inventory response for one AWS account and Region."""

    account_id: str = Field(pattern=r"^\d{12}$")
    region: str
    resource_count: int
    resources: list[EC2ResourceResponse]


class ConnectionCreateRequest(BaseModel):
    """Create an AWS role onboarding draft."""

    model_config = ConfigDict(extra="forbid")
    alias: str = Field(min_length=2, max_length=120)
    expected_account_id: str = Field(pattern=r"^\d{12}$")
    role_arn: str = Field(
        pattern=r"^arn:aws[a-zA-Z-]*:iam::\d{12}:role/[A-Za-z0-9+=,.@_/-]+$",
        max_length=2048,
    )


class ConnectionResponse(BaseModel):
    """Safe connection state; External ID is returned only for setup."""

    id: UUID
    alias: str
    expected_account_id: str
    role_arn: str
    status: ConnectionStatus
    external_id: str | None = None
    verified_at: datetime | None = None
