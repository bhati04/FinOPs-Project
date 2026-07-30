"""Contract tests for explicit AI advisory generation."""

from decimal import Decimal

import pytest

from cloudwise.ai_advisor.errors import AiAdvisorDisabledError, AiAdvisorOutputError
from cloudwise.ai_advisor.prompts import ADVISORY_DISCLAIMER
from cloudwise.ai_advisor.schemas import (
    AdvisoryContext,
    AdvisorySuggestion,
    EvidenceItem,
    MoneyAmount,
    ProviderAdvisoryResult,
    ResourceContext,
    VerifiedCalculation,
)
from cloudwise.ai_advisor.service import AiAdvisorService


def advisory_context() -> AdvisoryContext:
    """Create verified, non-secret recommendation context."""
    return AdvisoryContext(
        recommendation_reference="rec-123",
        title="Review an underutilized instance",
        category="rightsizing",
        severity="medium",
        rule_id="ec2-rightsize",
        rule_version="1.0",
        resource=ResourceContext(
            internal_reference="resource-456",
            service="EC2",
            resource_type="instance",
            region="us-east-1",
            display_name="application worker",
        ),
        calculation=VerifiedCalculation(
            current_monthly_cost=MoneyAmount(amount=Decimal("120.00"), currency="USD"),
            estimated_monthly_savings=MoneyAmount(amount=Decimal("35.00"), currency="USD"),
            estimate_type="usage_based",
            calculation_summary="Pricing and observed usage were evaluated by rule version 1.0.",
        ),
        evidence=[
            EvidenceItem(
                reference="cpu.avg.14d",
                metric="Average CPU utilization",
                value="8.2",
                unit="percent",
                period_days=14,
            )
        ],
        rule_risk_notes=["Confirm peak and seasonal demand before changing capacity."],
    )


def suggestion(*, evidence_reference: str = "cpu.avg.14d") -> AdvisorySuggestion:
    """Create a qualitative provider response."""
    return AdvisorySuggestion(
        summary="Review whether the instance size still matches observed demand.",
        business_impact="A review may identify avoidable infrastructure spend.",
        priority_reason="The verified utilization evidence warrants timely review.",
        risk_notes=["Account for peak and seasonal workload demand."],
        suggested_review_steps=["Ask the service owner to review capacity requirements."],
        verification_steps=["Compare performance evidence before and after any approved change."],
        evidence_references=[evidence_reference],
        disclaimer="provider supplied value",
    )


class FakeProvider:
    """Deterministic provider with a visible call count."""

    def __init__(self, result: AdvisorySuggestion) -> None:
        self.result = result
        self.calls = 0

    async def generate_suggestion(self, context: AdvisoryContext) -> ProviderAdvisoryResult:
        self.calls += 1
        return ProviderAdvisoryResult(
            suggestion=self.result,
            provider="bedrock",
            model_id="test-model",
            provider_request_id="request-1",
        )


async def test_disabled_service_does_not_call_provider() -> None:
    provider = FakeProvider(suggestion())
    service = AiAdvisorService(provider, enabled=False)

    with pytest.raises(AiAdvisorDisabledError):
        await service.generate_on_demand(advisory_context())

    assert provider.calls == 0


async def test_on_demand_result_preserves_verified_calculation() -> None:
    context = advisory_context()
    provider = FakeProvider(suggestion())
    service = AiAdvisorService(provider, enabled=True)

    result = await service.generate_on_demand(context)

    assert provider.calls == 1
    assert result.verified_calculation == context.calculation
    assert result.suggestion.disclaimer == ADVISORY_DISCLAIMER
    assert len(result.context_hash) == 64


async def test_unknown_evidence_reference_is_rejected() -> None:
    provider = FakeProvider(suggestion(evidence_reference="invented.reference"))
    service = AiAdvisorService(provider, enabled=True)

    with pytest.raises(AiAdvisorOutputError):
        await service.generate_on_demand(advisory_context())
