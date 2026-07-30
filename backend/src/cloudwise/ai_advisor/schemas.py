"""Strict schemas crossing the AI advisory boundary."""

from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Reject fields that could accidentally leak unreviewed data to a model."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class MoneyAmount(StrictModel):
    """A rule-engine-calculated monetary amount."""

    amount: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")


class VerifiedCalculation(StrictModel):
    """Authoritative values calculated outside the language model."""

    current_monthly_cost: MoneyAmount
    estimated_monthly_savings: MoneyAmount
    estimate_type: Literal["exact", "usage_based", "advisory"]
    calculation_summary: str = Field(min_length=1, max_length=500)


class EvidenceItem(StrictModel):
    """A bounded, referenceable fact produced by CloudWise analysis."""

    reference: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.:-]+$")
    metric: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=200)
    unit: str | None = Field(default=None, max_length=40)
    period_days: int | None = Field(default=None, ge=1, le=400)


class ResourceContext(StrictModel):
    """Minimal non-secret resource context permitted in an AI request."""

    internal_reference: str = Field(min_length=1, max_length=100)
    service: str = Field(min_length=1, max_length=80)
    resource_type: str = Field(min_length=1, max_length=100)
    region: str | None = Field(default=None, max_length=40)
    display_name: str | None = Field(default=None, max_length=200)


class AdvisoryContext(StrictModel):
    """Verified recommendation data sent only after an explicit user request."""

    recommendation_reference: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=80)
    severity: Literal["low", "medium", "high", "critical"]
    rule_id: str = Field(min_length=1, max_length=100)
    rule_version: str = Field(min_length=1, max_length=40)
    resource: ResourceContext
    calculation: VerifiedCalculation
    evidence: list[EvidenceItem] = Field(min_length=1, max_length=30)
    rule_risk_notes: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def validate_verified_context(self) -> Self:
        """Keep financial and evidence references internally consistent."""
        calculation = self.calculation
        if (
            calculation.current_monthly_cost.currency
            != calculation.estimated_monthly_savings.currency
        ):
            raise ValueError("calculation currencies must match")
        references = [item.reference for item in self.evidence]
        if len(references) != len(set(references)):
            raise ValueError("evidence references must be unique")
        return self


class AdvisorySuggestion(StrictModel):
    """Qualitative model output; deliberately contains no financial fields."""

    summary: str = Field(min_length=1, max_length=800)
    business_impact: str = Field(min_length=1, max_length=800)
    priority_reason: str = Field(min_length=1, max_length=500)
    risk_notes: list[str] = Field(min_length=1, max_length=8)
    suggested_review_steps: list[str] = Field(min_length=1, max_length=10)
    verification_steps: list[str] = Field(min_length=1, max_length=10)
    evidence_references: list[str] = Field(min_length=1, max_length=30)
    disclaimer: str = Field(min_length=1, max_length=300)


class ProviderAdvisoryResult(StrictModel):
    """Validated provider result plus non-sensitive trace metadata."""

    suggestion: AdvisorySuggestion
    provider: Literal["bedrock"]
    model_id: str = Field(min_length=1, max_length=300)
    provider_request_id: str | None = Field(default=None, max_length=200)


class OnDemandAdvisoryResult(StrictModel):
    """Service result preserving authoritative calculation provenance."""

    suggestion: AdvisorySuggestion
    verified_calculation: VerifiedCalculation
    provider: Literal["bedrock"]
    model_id: str
    provider_request_id: str | None = None
    context_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    prompt_version: str
