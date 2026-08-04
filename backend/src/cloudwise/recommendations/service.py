"""Deterministic tenant-scoped recommendation application service."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cloudwise.aws_accounts.models import AWSAccountConnection
from cloudwise.recommendations.models import (
    EstimateType,
    PricingStatus,
    Recommendation,
    RecommendationActivity,
    RecommendationActivityType,
    RecommendationEvaluation,
    RecommendationSeverity,
    RecommendationSource,
    RecommendationStatus,
)
from cloudwise.recommendations.pricing import (
    MockRecommendationPricingProvider,
    PricingProviderError,
    RecommendationPricingProvider,
    calculate_monthly_price,
)
from cloudwise.recommendations.rules import (
    RULE_SET_VERSION,
    RULES,
    InventoryEvidence,
    RuleEvaluation,
)
from cloudwise.recommendations.schemas import (
    RecommendationActivityResponse,
    RecommendationEvaluationResponse,
    RecommendationResponse,
)
from cloudwise.scans.models import InventoryResource

STATUS_TRANSITIONS: dict[RecommendationStatus, frozenset[RecommendationStatus]] = {
    RecommendationStatus.OPEN: frozenset(
        {
            RecommendationStatus.ACKNOWLEDGED,
            RecommendationStatus.DISMISSED,
            RecommendationStatus.RESOLVED,
        }
    ),
    RecommendationStatus.ACKNOWLEDGED: frozenset(
        {
            RecommendationStatus.OPEN,
            RecommendationStatus.DISMISSED,
            RecommendationStatus.RESOLVED,
        }
    ),
    RecommendationStatus.DISMISSED: frozenset(
        {RecommendationStatus.OPEN, RecommendationStatus.RESOLVED}
    ),
    RecommendationStatus.RESOLVED: frozenset({RecommendationStatus.OPEN}),
}


class RecommendationService:
    """Evaluate versioned rules and manage recommendation review state."""

    def __init__(
        self,
        session: AsyncSession,
        pricing_provider: RecommendationPricingProvider | None = None,
        pricing_stale_after: timedelta = timedelta(hours=48),
    ) -> None:
        self._session = session
        self._pricing_provider = pricing_provider or MockRecommendationPricingProvider()
        self._pricing_stale_after = pricing_stale_after

    async def evaluate(
        self,
        organization_id: UUID,
        requested_by_user_id: UUID,
        connection_id: UUID | None,
    ) -> RecommendationEvaluationResponse:
        """Evaluate active inventory without making customer AWS calls."""
        now = datetime.now(UTC)
        if connection_id is not None:
            scoped_connection = await self._session.scalar(
                select(AWSAccountConnection.id).where(
                    AWSAccountConnection.id == connection_id,
                    AWSAccountConnection.organization_id == organization_id,
                )
            )
            if scoped_connection is None:
                raise LookupError("AWS account connection was not found")
        resource_query = select(InventoryResource).where(
            InventoryResource.organization_id == organization_id,
            InventoryResource.is_active.is_(True),
            InventoryResource.resource_type.in_(tuple(rule.resource_type for rule in RULES)),
        )
        if connection_id is not None:
            resource_query = resource_query.where(InventoryResource.connection_id == connection_id)
        resources = (await self._session.scalars(resource_query)).all()

        existing_query = select(Recommendation).where(
            Recommendation.organization_id == organization_id
        )
        if connection_id is not None:
            existing_query = existing_query.where(Recommendation.connection_id == connection_id)
        existing = (await self._session.scalars(existing_query)).all()
        existing_by_key = {
            (item.inventory_resource_id, item.canonical_action): item for item in existing
        }
        evaluation = RecommendationEvaluation(
            organization_id=organization_id,
            connection_id=connection_id,
            requested_by_user_id=requested_by_user_id,
            rule_set_version=RULE_SET_VERSION,
            evaluated_resource_count=len(resources),
            eligible_recommendation_count=0,
            created_at=now,
            completed_at=now,
        )
        self._session.add(evaluation)
        await self._session.flush()

        eligible_keys: set[tuple[UUID, str]] = set()
        eligible_count = 0
        for resource in resources:
            evidence = self._inventory_evidence(resource)
            for rule in RULES:
                if rule.resource_type != resource.resource_type:
                    continue
                outcome = rule.evaluate(evidence)
                canonical_action = _canonical_action(rule.rule_id)
                key = (resource.id, canonical_action)
                if not outcome.eligible:
                    continue
                eligible_keys.add(key)
                eligible_count += 1
                recommendation = existing_by_key.get(key)
                if recommendation is None:
                    recommendation = self._new_recommendation(
                        organization_id,
                        evaluation.id,
                        resource,
                        rule.rule_id,
                        rule.version,
                        outcome,
                        now,
                    )
                    self._session.add(recommendation)
                    await self._session.flush()
                    await self._apply_pricing(recommendation, evidence, outcome, now)
                    self._add_status_activity(
                        recommendation,
                        None,
                        RecommendationStatus.OPEN,
                        None,
                        "Created by deterministic rule evaluation.",
                        now,
                    )
                    existing_by_key[key] = recommendation
                else:
                    previous_status = recommendation.status
                    recommendation.rule_id = rule.rule_id
                    recommendation.canonical_action = canonical_action
                    recommendation.sources = _add_source(
                        recommendation.sources, RecommendationSource.CLOUDWISE
                    )
                    source_metadata = dict(recommendation.source_metadata)
                    source_metadata[RecommendationSource.CLOUDWISE.value] = {
                        "rule_version": rule.version,
                        "observed_at": now.isoformat(),
                    }
                    recommendation.source_metadata = source_metadata
                    self._apply_outcome(
                        recommendation,
                        evaluation.id,
                        rule.version,
                        outcome,
                        resource.last_seen_at,
                        now,
                    )
                    await self._apply_pricing(recommendation, evidence, outcome, now)
                    if previous_status is RecommendationStatus.RESOLVED:
                        recommendation.status = RecommendationStatus.OPEN
                        recommendation.resolved_at = None
                        self._add_status_activity(
                            recommendation,
                            previous_status,
                            RecommendationStatus.OPEN,
                            None,
                            "Eligibility returned during deterministic evaluation.",
                            now,
                        )

        for recommendation in existing:
            key = (recommendation.inventory_resource_id, recommendation.canonical_action)
            if (
                RecommendationSource.CLOUDWISE.value in recommendation.sources
                and key not in eligible_keys
            ):
                recommendation.sources = [
                    source
                    for source in recommendation.sources
                    if source != RecommendationSource.CLOUDWISE.value
                ]
                source_metadata = dict(recommendation.source_metadata)
                source_metadata.pop(RecommendationSource.CLOUDWISE.value, None)
                recommendation.source_metadata = source_metadata
                if recommendation.sources:
                    recommendation.updated_at = now
                    recommendation.evaluation_id = evaluation.id
                    continue
                if recommendation.status is RecommendationStatus.RESOLVED:
                    continue
                previous_status = recommendation.status
                recommendation.status = RecommendationStatus.RESOLVED
                recommendation.resolved_at = now
                recommendation.updated_at = now
                recommendation.evaluation_id = evaluation.id
                self._add_status_activity(
                    recommendation,
                    previous_status,
                    RecommendationStatus.RESOLVED,
                    None,
                    "Rule eligibility is no longer present in active inventory.",
                    now,
                )

        evaluation.eligible_recommendation_count = eligible_count
        evaluation.completed_at = datetime.now(UTC)
        await self._session.commit()
        return self._evaluation_response(evaluation)

    async def list_recommendations(
        self,
        organization_id: UUID,
        status: RecommendationStatus | None,
        severity: RecommendationSeverity | None,
        connection_id: UUID | None,
    ) -> list[RecommendationResponse]:
        """List recommendation state without crossing tenant boundaries."""
        query = (
            select(Recommendation, InventoryResource)
            .join(InventoryResource, InventoryResource.id == Recommendation.inventory_resource_id)
            .where(Recommendation.organization_id == organization_id)
        )
        if status is not None:
            query = query.where(Recommendation.status == status)
        if severity is not None:
            query = query.where(Recommendation.severity == severity)
        if connection_id is not None:
            query = query.where(Recommendation.connection_id == connection_id)
        rows = (await self._session.execute(query.order_by(Recommendation.updated_at.desc()))).all()
        return [self._recommendation_response(item, resource) for item, resource in rows]

    async def update_status(
        self,
        organization_id: UUID,
        recommendation_id: UUID,
        actor_user_id: UUID,
        new_status: RecommendationStatus,
        comment: str | None,
    ) -> RecommendationResponse:
        """Apply one validated human lifecycle transition."""
        recommendation, resource = await self._get_scoped_recommendation(
            organization_id, recommendation_id
        )
        previous_status = recommendation.status
        if new_status is previous_status:
            raise ValueError("Recommendation already has the requested status")
        if new_status not in STATUS_TRANSITIONS[previous_status]:
            raise ValueError("Recommendation status transition is not allowed")
        now = datetime.now(UTC)
        recommendation.status = new_status
        recommendation.updated_at = now
        recommendation.resolved_at = now if new_status is RecommendationStatus.RESOLVED else None
        self._add_status_activity(
            recommendation,
            previous_status,
            new_status,
            actor_user_id,
            comment,
            now,
        )
        await self._session.commit()
        return self._recommendation_response(recommendation, resource)

    async def add_comment(
        self,
        organization_id: UUID,
        recommendation_id: UUID,
        actor_user_id: UUID,
        comment: str,
    ) -> RecommendationActivityResponse:
        """Append a tenant-scoped analyst comment without changing status."""
        recommendation, _ = await self._get_scoped_recommendation(
            organization_id, recommendation_id
        )
        activity = RecommendationActivity(
            organization_id=organization_id,
            recommendation_id=recommendation.id,
            actor_user_id=actor_user_id,
            activity_type=RecommendationActivityType.COMMENT,
            from_status=None,
            to_status=None,
            comment=comment,
            created_at=datetime.now(UTC),
        )
        self._session.add(activity)
        await self._session.commit()
        return self._activity_response(activity)

    async def list_activities(
        self,
        organization_id: UUID,
        recommendation_id: UUID,
    ) -> list[RecommendationActivityResponse]:
        """List append-only activity for one tenant-scoped recommendation."""
        await self._get_scoped_recommendation(organization_id, recommendation_id)
        activities = (
            await self._session.scalars(
                select(RecommendationActivity)
                .where(
                    RecommendationActivity.organization_id == organization_id,
                    RecommendationActivity.recommendation_id == recommendation_id,
                )
                .order_by(RecommendationActivity.created_at)
            )
        ).all()
        return [self._activity_response(activity) for activity in activities]

    async def _get_scoped_recommendation(
        self,
        organization_id: UUID,
        recommendation_id: UUID,
    ) -> tuple[Recommendation, InventoryResource]:
        row = (
            await self._session.execute(
                select(Recommendation, InventoryResource)
                .join(
                    InventoryResource,
                    InventoryResource.id == Recommendation.inventory_resource_id,
                )
                .where(
                    Recommendation.id == recommendation_id,
                    Recommendation.organization_id == organization_id,
                )
            )
        ).one_or_none()
        if row is None:
            raise LookupError("Recommendation was not found")
        return row[0], row[1]

    def _new_recommendation(
        self,
        organization_id: UUID,
        evaluation_id: UUID,
        resource: InventoryResource,
        rule_id: str,
        rule_version: str,
        outcome: RuleEvaluation,
        now: datetime,
    ) -> Recommendation:
        return Recommendation(
            organization_id=organization_id,
            connection_id=resource.connection_id,
            inventory_resource_id=resource.id,
            evaluation_id=evaluation_id,
            rule_id=rule_id,
            rule_version=rule_version,
            canonical_action=_canonical_action(rule_id),
            sources=[RecommendationSource.CLOUDWISE.value],
            source_metadata={
                RecommendationSource.CLOUDWISE.value: {
                    "rule_version": rule_version,
                    "observed_at": now.isoformat(),
                }
            },
            title=outcome.title,
            category=outcome.category,
            severity=outcome.severity,
            confidence=outcome.confidence,
            status=RecommendationStatus.OPEN,
            evidence=outcome.evidence,
            exclusions=outcome.exclusions,
            risk_notes=outcome.risk_notes,
            verification_steps=outcome.verification_steps,
            evidence_period_start=None,
            evidence_period_end=resource.last_seen_at,
            estimate_type=outcome.estimate_type,
            current_monthly_cost=None,
            estimated_monthly_savings=None,
            currency=None,
            pricing_status=PricingStatus.UNAVAILABLE,
            pricing_source=None,
            pricing_version=None,
            pricing_effective_at=None,
            pricing_retrieved_at=None,
            pricing_unavailable_reason="pricing_not_evaluated",
            calculation_inputs=[],
            calculation_summary=outcome.calculation_summary,
            created_at=now,
            updated_at=now,
            resolved_at=None,
        )

    @staticmethod
    def _apply_outcome(
        recommendation: Recommendation,
        evaluation_id: UUID,
        rule_version: str,
        outcome: RuleEvaluation,
        evidence_period_end: datetime,
        now: datetime,
    ) -> None:
        recommendation.evaluation_id = evaluation_id
        recommendation.rule_version = rule_version
        recommendation.title = outcome.title
        recommendation.category = outcome.category
        recommendation.severity = outcome.severity
        recommendation.confidence = outcome.confidence
        recommendation.evidence = outcome.evidence
        recommendation.exclusions = outcome.exclusions
        recommendation.risk_notes = outcome.risk_notes
        recommendation.verification_steps = outcome.verification_steps
        recommendation.evidence_period_end = evidence_period_end
        recommendation.estimate_type = outcome.estimate_type
        recommendation.calculation_summary = outcome.calculation_summary
        recommendation.updated_at = now

    async def _apply_pricing(
        self,
        recommendation: Recommendation,
        resource: InventoryEvidence,
        outcome: RuleEvaluation,
        now: datetime,
    ) -> None:
        try:
            quote = await self._pricing_provider.quote(resource)
            calculation = calculate_monthly_price(resource, quote)
        except PricingProviderError as exc:
            if (
                recommendation.current_monthly_cost is not None
                and recommendation.estimated_monthly_savings is not None
                and recommendation.pricing_retrieved_at is not None
            ):
                recommendation.pricing_status = PricingStatus.STALE
                recommendation.pricing_unavailable_reason = exc.error_code
                recommendation.estimate_type = EstimateType.USAGE_BASED
                recommendation.calculation_summary = (
                    "The previous list-price estimate was retained because "
                    "pricing could not be refreshed."
                )
                return
            recommendation.current_monthly_cost = None
            recommendation.estimated_monthly_savings = None
            recommendation.currency = None
            recommendation.pricing_status = PricingStatus.UNAVAILABLE
            recommendation.pricing_source = None
            recommendation.pricing_version = None
            recommendation.pricing_effective_at = None
            recommendation.pricing_retrieved_at = None
            recommendation.pricing_unavailable_reason = exc.error_code
            recommendation.calculation_inputs = []
            recommendation.estimate_type = outcome.estimate_type
            recommendation.calculation_summary = outcome.calculation_summary
            return
        quote_age = now - quote.retrieved_at
        recommendation.current_monthly_cost = calculation.monthly_cost
        recommendation.estimated_monthly_savings = calculation.monthly_cost
        recommendation.currency = quote.currency
        recommendation.pricing_status = (
            PricingStatus.STALE
            if quote_age > self._pricing_stale_after
            else PricingStatus.AVAILABLE
        )
        recommendation.pricing_source = quote.source
        recommendation.pricing_version = quote.version
        recommendation.pricing_effective_at = quote.effective_at
        recommendation.pricing_retrieved_at = quote.retrieved_at
        recommendation.pricing_unavailable_reason = (
            "pricing_quote_stale" if recommendation.pricing_status is PricingStatus.STALE else None
        )
        recommendation.calculation_inputs = calculation.inputs
        recommendation.estimate_type = EstimateType.USAGE_BASED
        recommendation.calculation_summary = calculation.summary

    def _add_status_activity(
        self,
        recommendation: Recommendation,
        from_status: RecommendationStatus | None,
        to_status: RecommendationStatus,
        actor_user_id: UUID | None,
        comment: str | None,
        created_at: datetime,
    ) -> None:
        self._session.add(
            RecommendationActivity(
                organization_id=recommendation.organization_id,
                recommendation_id=recommendation.id,
                actor_user_id=actor_user_id,
                activity_type=RecommendationActivityType.STATUS_CHANGED,
                from_status=from_status,
                to_status=to_status,
                comment=comment,
                created_at=created_at,
            )
        )

    @staticmethod
    def _inventory_evidence(resource: InventoryResource) -> InventoryEvidence:
        return InventoryEvidence(
            id=resource.id,
            connection_id=resource.connection_id,
            resource_type=resource.resource_type,
            name=resource.name,
            state=resource.state,
            region=resource.region,
            details=resource.details,
            last_seen_at=resource.last_seen_at,
        )

    @staticmethod
    def _evaluation_response(
        evaluation: RecommendationEvaluation,
    ) -> RecommendationEvaluationResponse:
        return RecommendationEvaluationResponse(
            id=evaluation.id,
            connection_id=evaluation.connection_id,
            rule_set_version=evaluation.rule_set_version,
            evaluated_resource_count=evaluation.evaluated_resource_count,
            eligible_recommendation_count=evaluation.eligible_recommendation_count,
            created_at=evaluation.created_at,
            completed_at=evaluation.completed_at,
        )

    @staticmethod
    def _recommendation_response(
        recommendation: Recommendation,
        resource: InventoryResource,
    ) -> RecommendationResponse:
        return RecommendationResponse(
            id=recommendation.id,
            connection_id=recommendation.connection_id,
            inventory_resource_id=recommendation.inventory_resource_id,
            resource_type=resource.resource_type,
            resource_name=resource.name,
            region=resource.region,
            rule_id=recommendation.rule_id,
            rule_version=recommendation.rule_version,
            canonical_action=recommendation.canonical_action,
            sources=recommendation.sources,
            source_metadata=recommendation.source_metadata,
            title=recommendation.title,
            category=recommendation.category,
            severity=recommendation.severity,
            confidence=recommendation.confidence,
            status=recommendation.status,
            evidence=recommendation.evidence,
            exclusions=recommendation.exclusions,
            risk_notes=recommendation.risk_notes,
            verification_steps=recommendation.verification_steps,
            evidence_period_start=recommendation.evidence_period_start,
            evidence_period_end=recommendation.evidence_period_end,
            estimate_type=recommendation.estimate_type,
            current_monthly_cost=recommendation.current_monthly_cost,
            estimated_monthly_savings=recommendation.estimated_monthly_savings,
            currency=recommendation.currency,
            pricing_status=recommendation.pricing_status,
            pricing_source=recommendation.pricing_source,
            pricing_version=recommendation.pricing_version,
            pricing_effective_at=recommendation.pricing_effective_at,
            pricing_retrieved_at=recommendation.pricing_retrieved_at,
            pricing_unavailable_reason=recommendation.pricing_unavailable_reason,
            calculation_inputs=recommendation.calculation_inputs,
            calculation_summary=recommendation.calculation_summary,
            created_at=recommendation.created_at,
            updated_at=recommendation.updated_at,
            resolved_at=recommendation.resolved_at,
        )

    @staticmethod
    def _activity_response(
        activity: RecommendationActivity,
    ) -> RecommendationActivityResponse:
        return RecommendationActivityResponse(
            id=activity.id,
            actor_user_id=activity.actor_user_id,
            activity_type=activity.activity_type,
            from_status=activity.from_status,
            to_status=activity.to_status,
            comment=activity.comment,
            created_at=activity.created_at,
        )


def _canonical_action(rule_id: str) -> str:
    return {
        "ebs.unattached_volume": "delete",
        "ec2.unassociated_elastic_ip": "release",
    }.get(rule_id, rule_id)


def _add_source(sources: list[str], source: RecommendationSource) -> list[str]:
    return list(dict.fromkeys([*sources, source.value]))
