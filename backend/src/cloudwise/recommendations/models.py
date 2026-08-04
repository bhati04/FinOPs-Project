"""Persisted recommendation, evaluation, and activity models."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from cloudwise.core.database import Base


class RecommendationStatus(StrEnum):
    """Human-review lifecycle for a recommendation."""

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    DISMISSED = "dismissed"
    RESOLVED = "resolved"


class RecommendationSeverity(StrEnum):
    """Rule-owned review priority."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EstimateType(StrEnum):
    """Provenance of a recommendation's financial estimate."""

    EXACT = "exact"
    USAGE_BASED = "usage_based"
    ADVISORY = "advisory"


class PricingStatus(StrEnum):
    """Availability of verified pricing attached to a recommendation."""

    AVAILABLE = "available"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class RecommendationActivityType(StrEnum):
    """Auditable recommendation activity categories."""

    STATUS_CHANGED = "status_changed"
    COMMENT = "comment"


class RecommendationSource(StrEnum):
    """Trusted producers that contributed to a canonical finding."""

    CLOUDWISE = "cloudwise"
    COST_OPTIMIZATION_HUB = "cost_optimization_hub"
    COMPUTE_OPTIMIZER = "compute_optimizer"


class RecommendationSyncStatus(StrEnum):
    """Lifecycle of a read-only AWS recommendation import."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class RecommendationEvaluation(Base):
    """One deterministic rule-set evaluation."""

    __tablename__ = "recommendation_evaluations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    connection_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("aws_account_connections.id", ondelete="CASCADE"), index=True
    )
    requested_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    rule_set_version: Mapped[str] = mapped_column(String(40))
    evaluated_resource_count: Mapped[int]
    eligible_recommendation_count: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Recommendation(Base):
    """Current state and rule evidence for one resource finding."""

    __tablename__ = "recommendations"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "inventory_resource_id",
            "rule_id",
            name="uq_recommendations_resource_rule",
        ),
        UniqueConstraint(
            "organization_id",
            "inventory_resource_id",
            "canonical_action",
            name="uq_recommendations_resource_action",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("aws_account_connections.id", ondelete="CASCADE"), index=True
    )
    inventory_resource_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_resources.id", ondelete="CASCADE"), index=True
    )
    evaluation_id: Mapped[UUID] = mapped_column(
        ForeignKey("recommendation_evaluations.id", ondelete="CASCADE"), index=True
    )
    rule_id: Mapped[str] = mapped_column(String(100))
    rule_version: Mapped[str] = mapped_column(String(40))
    canonical_action: Mapped[str] = mapped_column(String(80))
    sources: Mapped[list[str]] = mapped_column(JSON)
    source_metadata: Mapped[dict[str, object]] = mapped_column(JSON)
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(80))
    severity: Mapped[RecommendationSeverity] = mapped_column(
        Enum(RecommendationSeverity, name="recommendation_severity")
    )
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    status: Mapped[RecommendationStatus] = mapped_column(
        Enum(RecommendationStatus, name="recommendation_status"), index=True
    )
    evidence: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    exclusions: Mapped[list[str]] = mapped_column(JSON)
    risk_notes: Mapped[list[str]] = mapped_column(JSON)
    verification_steps: Mapped[list[str]] = mapped_column(JSON)
    evidence_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    estimate_type: Mapped[EstimateType] = mapped_column(
        Enum(EstimateType, name="recommendation_estimate_type")
    )
    current_monthly_cost: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    estimated_monthly_savings: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    currency: Mapped[str | None] = mapped_column(String(8))
    pricing_status: Mapped[PricingStatus] = mapped_column(
        Enum(PricingStatus, name="recommendation_pricing_status")
    )
    pricing_source: Mapped[str | None] = mapped_column(String(40))
    pricing_version: Mapped[str | None] = mapped_column(String(80))
    pricing_effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pricing_retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pricing_unavailable_reason: Mapped[str | None] = mapped_column(String(80))
    calculation_inputs: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    calculation_summary: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RecommendationSourceSync(Base):
    """One tenant-scoped import from AWS recommendation services."""

    __tablename__ = "recommendation_source_syncs"
    __table_args__ = (
        Index(
            "ix_recommendation_source_syncs_active_connection",
            "connection_id",
            unique=True,
            postgresql_where=text("status IN ('QUEUED', 'RUNNING')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("aws_account_connections.id", ondelete="CASCADE"), index=True
    )
    requested_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    region: Mapped[str] = mapped_column(String(30))
    status: Mapped[RecommendationSyncStatus] = mapped_column(
        Enum(RecommendationSyncStatus, name="recommendation_sync_status")
    )
    imported_count: Mapped[int]
    matched_resource_count: Mapped[int]
    unmatched_resource_count: Mapped[int]
    deduplicated_count: Mapped[int]
    completed_sources: Mapped[list[str]] = mapped_column(JSON)
    failed_sources: Mapped[list[str]] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RecommendationActivity(Base):
    """Append-only status or comment activity."""

    __tablename__ = "recommendation_activities"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    recommendation_id: Mapped[UUID] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE"), index=True
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    activity_type: Mapped[RecommendationActivityType] = mapped_column(
        Enum(RecommendationActivityType, name="recommendation_activity_type")
    )
    from_status: Mapped[RecommendationStatus | None] = mapped_column(
        Enum(RecommendationStatus, name="recommendation_status")
    )
    to_status: Mapped[RecommendationStatus | None] = mapped_column(
        Enum(RecommendationStatus, name="recommendation_status")
    )
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
