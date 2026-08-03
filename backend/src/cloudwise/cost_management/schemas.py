"""Public Cost Explorer synchronization schemas."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from cloudwise.cost_management.models import CostGranularity, CostGrouping, CostSyncStatus


class CostSyncResponse(BaseModel):
    """Safe cost synchronization state."""

    id: UUID
    connection_id: UUID
    status: CostSyncStatus
    record_count: int
    error_code: str | None
    failed_facets: list[str]
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class CostAggregateResponse(BaseModel):
    """One persisted cost grouping."""

    connection_id: UUID
    period_start: date
    granularity: CostGranularity
    grouping: CostGrouping
    service: str
    region: str
    usage_type: str
    tag_key: str
    tag_value: str
    amount: Decimal
    currency: str


class CostForecastResponse(BaseModel):
    """One persisted Cost Explorer forecast period."""

    connection_id: UUID
    period_start: date
    period_end: date
    granularity: CostGranularity
    mean_amount: Decimal
    lower_bound: Decimal
    upper_bound: Decimal
    currency: str
