"""Public response schemas for AWS account endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


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
