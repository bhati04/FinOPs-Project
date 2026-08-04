"""Recommendation service tenant and lifecycle tests."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cloudwise.recommendations.models import (
    PricingStatus,
    RecommendationSource,
    RecommendationStatus,
)
from cloudwise.recommendations.pricing import (
    MockRecommendationPricingProvider,
    PriceQuote,
    PricingProviderError,
)
from cloudwise.recommendations.rules import UnattachedEbsVolumeRule
from cloudwise.recommendations.service import STATUS_TRANSITIONS, RecommendationService
from cloudwise.scans.models import InventoryResource


class FailedPricingProvider:
    """Pricing provider fixture that returns only a safe failure code."""

    async def quote(self, resource: object) -> PriceQuote:
        raise PricingProviderError("pricing_provider_unavailable")


async def test_evaluation_rejects_connection_outside_organization() -> None:
    """A tenant cannot evaluate another organization's connection."""
    session = AsyncMock()
    session.scalar.return_value = None

    with pytest.raises(LookupError):
        await RecommendationService(session).evaluate(uuid4(), uuid4(), uuid4())

    session.add.assert_not_called()


def test_resolved_recommendations_can_only_be_reopened() -> None:
    """Resolved findings cannot jump directly to another terminal state."""
    assert STATUS_TRANSITIONS[RecommendationStatus.RESOLVED] == frozenset(
        {RecommendationStatus.OPEN}
    )


async def test_pricing_refresh_failure_preserves_previous_estimate_as_stale() -> None:
    """A transient catalog failure cannot erase a previously verified amount."""
    now = datetime(2026, 8, 4, tzinfo=UTC)
    resource = InventoryResource(
        id=uuid4(),
        organization_id=uuid4(),
        connection_id=uuid4(),
        scan_id=uuid4(),
        region="us-east-1",
        resource_type="ebs_volume",
        resource_id="vol-example",
        name="example",
        state="available",
        details={
            "attachments": [],
            "volume_type": "gp2",
            "size_gib": 100,
            "iops": 300,
        },
        discovered_at=now,
        is_active=True,
        last_seen_at=now,
        inactive_at=None,
    )
    session = AsyncMock()
    service = RecommendationService(session, MockRecommendationPricingProvider())
    evidence = service._inventory_evidence(resource)
    outcome = UnattachedEbsVolumeRule().evaluate(evidence)
    recommendation = service._new_recommendation(
        resource.organization_id,
        uuid4(),
        resource,
        "ebs.unattached_volume",
        "1.1.0",
        outcome,
        now,
    )

    await service._apply_pricing(recommendation, evidence, outcome, now)

    available_status = recommendation.pricing_status
    assert recommendation.canonical_action == "delete"
    assert recommendation.sources == [RecommendationSource.CLOUDWISE.value]
    assert available_status is PricingStatus.AVAILABLE
    assert recommendation.current_monthly_cost == Decimal("10.00000000")
    failed_service = RecommendationService(session, FailedPricingProvider())

    await failed_service._apply_pricing(recommendation, evidence, outcome, now)

    stale_status = recommendation.pricing_status
    assert stale_status is PricingStatus.STALE
    assert recommendation.current_monthly_cost == Decimal("10.00000000")
    assert recommendation.pricing_unavailable_reason == "pricing_provider_unavailable"
