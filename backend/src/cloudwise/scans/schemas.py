"""Public schemas for inventory scan orchestration."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from cloudwise.scans.models import ScanStatus


class InventoryScanResponse(BaseModel):
    """Safe organization-scoped scan state."""

    id: UUID
    connection_id: UUID
    region: str
    status: ScanStatus
    resource_count: int
    error_code: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class InventoryResourceResponse(BaseModel):
    """Normalized resource discovered by a completed scan."""

    id: UUID
    connection_id: UUID
    scan_id: UUID
    region: str
    resource_type: str
    resource_id: str
    name: str
    state: str
    details: dict[str, Any]
    discovered_at: datetime
