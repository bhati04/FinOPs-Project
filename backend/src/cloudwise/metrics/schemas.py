"""Public CloudWatch resource metric schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from cloudwise.metrics.models import MetricSyncStatus


class MetricSyncResponse(BaseModel):
    """Safe CloudWatch synchronization state."""

    id: UUID
    connection_id: UUID
    region: str
    status: MetricSyncStatus
    window_start: datetime
    window_end: datetime
    record_count: int
    failed_batch_count: int
    error_code: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ResourceMetricResponse(BaseModel):
    """One tenant-scoped resource metric datapoint."""

    inventory_resource_id: UUID
    resource_type: str
    resource_name: str
    region: str
    namespace: str
    metric_name: str
    statistic: str
    unit: str
    timestamp: datetime
    value: Decimal
