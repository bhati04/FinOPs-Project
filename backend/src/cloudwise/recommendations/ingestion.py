"""Canonicalize and deduplicate normalized AWS recommendation findings."""

from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cloudwise.recommendations.external import ExternalRecommendation
from cloudwise.recommendations.models import (
    EstimateType,
    PricingStatus,
    Recommendation,
    RecommendationEvaluation,
    RecommendationSeverity,
    RecommendationSource,
    RecommendationSourceSync,
    RecommendationStatus,
)
from cloudwise.scans.models import InventoryResource

SOURCE_ORDER = (
    RecommendationSource.CLOUDWISE.value,
    RecommendationSource.COST_OPTIMIZATION_HUB.value,
    RecommendationSource.COMPUTE_OPTIMIZER.value,
)


async def merge_external_recommendations(
    session: AsyncSession,
    sync: RecommendationSourceSync,
    findings: list[ExternalRecommendation],
    completed_sources: set[RecommendationSource],
) -> tuple[int, int, int, int]:
    """Merge source observations by organization, resource, and action."""
    now = datetime.now(UTC)
    resources = list(
        (
            await session.scalars(
                select(InventoryResource).where(
                    InventoryResource.organization_id == sync.organization_id,
                    InventoryResource.connection_id == sync.connection_id,
                    InventoryResource.is_active.is_(True),
                )
            )
        ).all()
    )
    recommendations = list(
        (
            await session.scalars(
                select(Recommendation).where(
                    Recommendation.organization_id == sync.organization_id,
                    Recommendation.connection_id == sync.connection_id,
                )
            )
        ).all()
    )
    evaluation = RecommendationEvaluation(
        organization_id=sync.organization_id,
        connection_id=sync.connection_id,
        requested_by_user_id=sync.requested_by_user_id,
        rule_set_version="aws-import-1.0.0",
        evaluated_resource_count=len(resources),
        eligible_recommendation_count=0,
        created_at=now,
        completed_at=now,
    )
    session.add(evaluation)
    await session.flush()

    resource_index = _resource_index(resources)
    recommendation_index = {
        (item.inventory_resource_id, item.canonical_action): item for item in recommendations
    }
    seen: dict[RecommendationSource, set[tuple[object, str]]] = defaultdict(set)
    imported = matched = unmatched = deduplicated = 0

    ordered = sorted(
        findings,
        key=lambda item: 0 if item.source is RecommendationSource.COST_OPTIMIZATION_HUB else 1,
    )
    for finding in ordered:
        resource = _match_resource(resource_index, finding)
        if resource is None:
            unmatched += 1
            continue
        matched += 1
        key = (resource.id, finding.canonical_action)
        seen[finding.source].add(key)
        recommendation = recommendation_index.get(key)
        if recommendation is None:
            recommendation = _new_external_recommendation(sync, evaluation, resource, finding, now)
            session.add(recommendation)
            recommendation_index[key] = recommendation
            recommendations.append(recommendation)
            imported += 1
        else:
            if finding.source.value not in recommendation.sources:
                deduplicated += 1
            _attach_source(recommendation, finding, now)
            imported += 1

    for recommendation in recommendations:
        key = (recommendation.inventory_resource_id, recommendation.canonical_action)
        sources = list(recommendation.sources)
        metadata = dict(recommendation.source_metadata)
        removed_primary = False
        for source in completed_sources:
            if source.value in sources and key not in seen[source]:
                sources.remove(source.value)
                metadata.pop(source.value, None)
                removed_primary = (
                    removed_primary or recommendation.pricing_source == _pricing_source(source)
                )
        recommendation.sources = _ordered_sources(sources)
        recommendation.source_metadata = metadata
        if not sources and recommendation.status is not RecommendationStatus.RESOLVED:
            recommendation.status = RecommendationStatus.RESOLVED
            recommendation.resolved_at = now
            recommendation.updated_at = now
        if removed_primary:
            recommendation.pricing_status = PricingStatus.UNAVAILABLE
            recommendation.pricing_unavailable_reason = "external_source_no_longer_reported"
            recommendation.pricing_source = None
            recommendation.pricing_version = None
            recommendation.pricing_effective_at = None
            recommendation.pricing_retrieved_at = None
            recommendation.current_monthly_cost = None
            recommendation.estimated_monthly_savings = None
            recommendation.currency = None
    evaluation.eligible_recommendation_count = imported
    return imported, matched, unmatched, deduplicated


def _resource_index(
    resources: list[InventoryResource],
) -> dict[tuple[str, str], list[InventoryResource]]:
    index: dict[tuple[str, str], list[InventoryResource]] = defaultdict(list)
    for resource in resources:
        index[(resource.resource_type, resource.resource_id)].append(resource)
        terminal = _terminal_identifier(resource.resource_id)
        if terminal != resource.resource_id:
            index[(resource.resource_type, terminal)].append(resource)
    return index


def _match_resource(
    index: dict[tuple[str, str], list[InventoryResource]],
    finding: ExternalRecommendation,
) -> InventoryResource | None:
    identifiers = {
        finding.resource_id,
        _terminal_identifier(finding.resource_id),
    }
    if finding.resource_arn:
        identifiers.update({finding.resource_arn, _terminal_identifier(finding.resource_arn)})
    candidates: list[InventoryResource] = []
    for identifier in identifiers:
        candidates.extend(index.get((finding.resource_type, identifier), []))
    unique = {item.id: item for item in candidates}
    if finding.region != "global":
        regional = [item for item in unique.values() if item.region == finding.region]
        if len(regional) == 1:
            return regional[0]
    return next(iter(unique.values())) if len(unique) == 1 else None


def _new_external_recommendation(
    sync: RecommendationSourceSync,
    evaluation: RecommendationEvaluation,
    resource: InventoryResource,
    finding: ExternalRecommendation,
    now: datetime,
) -> Recommendation:
    metadata = {finding.source.value: _source_metadata(finding, now)}
    return Recommendation(
        organization_id=sync.organization_id,
        connection_id=sync.connection_id,
        inventory_resource_id=resource.id,
        evaluation_id=evaluation.id,
        rule_id=f"aws.{finding.source.value}.{finding.canonical_action}",
        rule_version="1.0.0",
        canonical_action=finding.canonical_action,
        sources=[finding.source.value],
        source_metadata=metadata,
        title=finding.title,
        category="aws_optimization",
        severity=_severity(finding.estimated_monthly_savings),
        confidence=finding.confidence,
        status=RecommendationStatus.OPEN,
        evidence=_evidence(finding),
        exclusions=[],
        risk_notes=[
            "Validate workload performance, availability, and rollback requirements before change."
        ],
        verification_steps=[
            "Review the current and recommended configurations in AWS.",
            "Validate the recommendation against workload owners and recent utilization.",
            "Use an approved change process; CloudWise does not execute this action.",
        ],
        evidence_period_start=None,
        evidence_period_end=finding.last_refreshed_at,
        estimate_type=EstimateType.USAGE_BASED,
        current_monthly_cost=finding.current_monthly_cost,
        estimated_monthly_savings=finding.estimated_monthly_savings,
        currency=finding.currency,
        pricing_status=(
            PricingStatus.AVAILABLE
            if finding.estimated_monthly_savings is not None and finding.currency
            else PricingStatus.UNAVAILABLE
        ),
        pricing_source=_pricing_source(finding.source),
        pricing_version=finding.last_refreshed_at.isoformat(),
        pricing_effective_at=finding.last_refreshed_at,
        pricing_retrieved_at=now,
        pricing_unavailable_reason=(
            None
            if finding.estimated_monthly_savings is not None and finding.currency
            else "external_estimate_unavailable"
        ),
        calculation_inputs=_calculation_inputs(finding),
        calculation_summary=(
            "AWS usage-based estimate imported read-only; discounts depend on the source settings."
        ),
        created_at=now,
        updated_at=now,
        resolved_at=None,
    )


def _attach_source(
    recommendation: Recommendation,
    finding: ExternalRecommendation,
    now: datetime,
) -> None:
    sources = set(recommendation.sources)
    sources.add(finding.source.value)
    metadata = dict(recommendation.source_metadata)
    metadata[finding.source.value] = _source_metadata(finding, now)
    recommendation.sources = _ordered_sources(sources)
    recommendation.source_metadata = metadata
    recommendation.evidence_period_end = max(
        recommendation.evidence_period_end, finding.last_refreshed_at
    )
    recommendation.updated_at = now
    if finding.source is RecommendationSource.COST_OPTIMIZATION_HUB or (
        recommendation.pricing_source not in {"aws_cost_optimization_hub"}
    ):
        recommendation.current_monthly_cost = finding.current_monthly_cost
        recommendation.estimated_monthly_savings = finding.estimated_monthly_savings
        recommendation.currency = finding.currency
        recommendation.pricing_source = _pricing_source(finding.source)
        recommendation.pricing_version = finding.last_refreshed_at.isoformat()
        recommendation.pricing_effective_at = finding.last_refreshed_at
        recommendation.pricing_retrieved_at = now
        recommendation.pricing_status = (
            PricingStatus.AVAILABLE
            if finding.estimated_monthly_savings is not None and finding.currency
            else PricingStatus.UNAVAILABLE
        )
        recommendation.pricing_unavailable_reason = (
            None
            if recommendation.pricing_status is PricingStatus.AVAILABLE
            else "external_estimate_unavailable"
        )
        recommendation.calculation_inputs = _calculation_inputs(finding)
        recommendation.calculation_summary = (
            "AWS usage-based estimate imported read-only; discounts depend on the source settings."
        )


def _source_metadata(finding: ExternalRecommendation, observed_at: datetime) -> dict[str, object]:
    return {
        "recommendation_id": finding.source_recommendation_id,
        "last_refreshed_at": finding.last_refreshed_at.isoformat(),
        "observed_at": observed_at.isoformat(),
        "recommended_summary": finding.recommended_summary,
        "implementation_effort": finding.implementation_effort,
        "restart_needed": finding.restart_needed,
        "rollback_possible": finding.rollback_possible,
    }


def _evidence(finding: ExternalRecommendation) -> list[dict[str, object]]:
    return [
        {"field": "source", "value": finding.source.value},
        {"field": "current_configuration", "value": finding.current_summary},
        {"field": "recommended_configuration", "value": finding.recommended_summary},
        {"field": "lookback_days", "value": finding.lookback_days},
        {"field": "savings_percentage", "value": _json_decimal(finding.savings_percentage)},
    ]


def _calculation_inputs(finding: ExternalRecommendation) -> list[dict[str, object]]:
    return [
        {"name": "current_monthly_cost", "value": _json_decimal(finding.current_monthly_cost)},
        {
            "name": "estimated_monthly_savings",
            "value": _json_decimal(finding.estimated_monthly_savings),
        },
        {"name": "savings_percentage", "value": _json_decimal(finding.savings_percentage)},
        {"name": "currency", "value": finding.currency},
    ]


def _terminal_identifier(value: str) -> str:
    return value.replace(":function:", "/").rsplit("/", 1)[-1]


def _pricing_source(source: RecommendationSource) -> str:
    return (
        "aws_cost_optimization_hub"
        if source is RecommendationSource.COST_OPTIMIZATION_HUB
        else "aws_compute_optimizer"
    )


def _severity(savings: Decimal | None) -> RecommendationSeverity:
    if savings is None:
        return RecommendationSeverity.LOW
    if savings >= Decimal("1000"):
        return RecommendationSeverity.CRITICAL
    if savings >= Decimal("250"):
        return RecommendationSeverity.HIGH
    if savings >= Decimal("50"):
        return RecommendationSeverity.MEDIUM
    return RecommendationSeverity.LOW


def _ordered_sources(sources: Iterable[str]) -> list[str]:
    source_set = set(sources)
    return [source for source in SOURCE_ORDER if source in source_set]


def _json_decimal(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None
