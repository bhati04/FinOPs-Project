"""Public recommendation engine schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from cloudwise.recommendations.models import (
    EstimateType,
    PricingStatus,
    RecommendationActivityType,
    RecommendationSeverity,
    RecommendationSource,
    RecommendationStatus,
    RecommendationSyncStatus,
)


class RecommendationEvaluationResponse(BaseModel):
    """Summary of one deterministic rule-set evaluation."""

    id: UUID
    connection_id: UUID | None
    rule_set_version: str
    evaluated_resource_count: int
    eligible_recommendation_count: int
    created_at: datetime
    completed_at: datetime


class RecommendationResponse(BaseModel):
    """Explainable organization-scoped recommendation state."""

    id: UUID
    connection_id: UUID
    inventory_resource_id: UUID
    resource_type: str
    resource_name: str
    region: str
    rule_id: str
    rule_version: str
    canonical_action: str
    sources: list[RecommendationSource]
    source_metadata: dict[str, object]
    title: str
    category: str
    severity: RecommendationSeverity
    confidence: Decimal
    status: RecommendationStatus
    evidence: list[dict[str, object]]
    exclusions: list[str]
    risk_notes: list[str]
    verification_steps: list[str]
    evidence_period_start: datetime | None
    evidence_period_end: datetime
    estimate_type: EstimateType
    current_monthly_cost: Decimal | None
    estimated_monthly_savings: Decimal | None
    currency: str | None
    pricing_status: PricingStatus
    pricing_source: str | None
    pricing_version: str | None
    pricing_effective_at: datetime | None
    pricing_retrieved_at: datetime | None
    pricing_unavailable_reason: str | None
    calculation_inputs: list[dict[str, object]]
    calculation_summary: str
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class RecommendationStatusUpdate(BaseModel):
    """Validated human lifecycle transition."""

    model_config = ConfigDict(str_strip_whitespace=True)

    status: RecommendationStatus
    comment: str | None = Field(default=None, min_length=1, max_length=1000)


class RecommendationCommentCreate(BaseModel):
    """Validated analyst comment."""

    model_config = ConfigDict(str_strip_whitespace=True)

    comment: str = Field(min_length=1, max_length=1000)


class RecommendationActivityResponse(BaseModel):
    """Append-only recommendation status or comment activity."""

    id: UUID
    actor_user_id: UUID | None
    activity_type: RecommendationActivityType
    from_status: RecommendationStatus | None
    to_status: RecommendationStatus | None
    comment: str | None
    created_at: datetime


class RecommendationSourceSyncResponse(BaseModel):
    """Safe progress and outcome for an AWS recommendation import."""

    id: UUID
    connection_id: UUID
    region: str
    status: RecommendationSyncStatus
    imported_count: int
    matched_resource_count: int
    unmatched_resource_count: int
    deduplicated_count: int
    completed_sources: list[str]
    failed_sources: list[str]
    error_code: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
