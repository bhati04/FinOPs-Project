"""Read-only AWS recommendation providers and normalized contracts."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from cloudwise.aws_accounts.provider import AWS_CLIENT_CONFIG, AWSProvider
from cloudwise.recommendations.models import RecommendationSource


class RecommendationProviderError(RuntimeError):
    """A safe provider failure without AWS response details."""

    def __init__(self, source: RecommendationSource, error_code: str) -> None:
        super().__init__(error_code)
        self.source = source
        self.error_code = error_code


@dataclass(frozen=True)
class ExternalRecommendation:
    """Provider-neutral, bounded recommendation evidence."""

    source: RecommendationSource
    source_recommendation_id: str
    resource_type: str
    resource_id: str
    resource_arn: str | None
    region: str
    canonical_action: str
    title: str
    current_summary: str
    recommended_summary: str
    current_monthly_cost: Decimal | None
    estimated_monthly_savings: Decimal | None
    currency: str | None
    savings_percentage: Decimal | None
    implementation_effort: str | None
    restart_needed: bool | None
    rollback_possible: bool | None
    lookback_days: int | None
    last_refreshed_at: datetime
    confidence: Decimal


RESOURCE_TYPES = {
    "Ec2Instance": "ec2_instance",
    "LambdaFunction": "lambda_function",
    "EbsVolume": "ebs_volume",
    "RdsDbInstance": "rds_instance",
    "NatGateway": "nat_gateway",
}

ACTION_TYPES = {
    "Rightsize": "rightsize",
    "Stop": "stop",
    "Upgrade": "upgrade",
    "PurchaseSavingsPlans": "purchase_commitment",
    "PurchaseReservedInstances": "purchase_commitment",
    "MigrateToGraviton": "migrate_to_graviton",
    "Delete": "delete",
    "ScaleIn": "scale_in",
}


class AWSCostOptimizationHubProvider:
    """Import AWS-deduplicated savings opportunities from the global endpoint."""

    source = RecommendationSource.COST_OPTIMIZATION_HUB

    def __init__(self, provider: AWSProvider) -> None:
        self._client = provider.session.client(
            "cost-optimization-hub",
            region_name="us-east-1",
            config=AWS_CLIENT_CONFIG,
        )

    def collect(self, account_id: str) -> list[ExternalRecommendation]:
        """Return all supported, already-deduplicated recommendations."""
        try:
            items: list[dict[str, Any]] = []
            next_token: str | None = None
            while True:
                request: dict[str, Any] = {
                    "filter": {"accountIds": [account_id]},
                    "includeAllRecommendations": False,
                    "maxResults": 1000,
                }
                if next_token:
                    request["nextToken"] = next_token
                response = self._client.list_recommendations(**request)
                items.extend(response.get("items", []))
                next_token = response.get("nextToken")
                if not next_token:
                    break
            return [item for raw in items if (item := _normalize_hub(raw)) is not None]
        except (ClientError, BotoCoreError, KeyError, TypeError, ValueError) as exc:
            raise RecommendationProviderError(
                self.source, "COST_OPTIMIZATION_HUB_UNAVAILABLE"
            ) from exc


class AWSComputeOptimizerProvider:
    """Regional EC2 and EBS fallback provider."""

    source = RecommendationSource.COMPUTE_OPTIMIZER

    def __init__(self, provider: AWSProvider) -> None:
        self._region = provider.region
        self._client = provider.session.client(
            "compute-optimizer",
            region_name=provider.region,
            config=AWS_CLIENT_CONFIG,
        )

    def collect(self) -> tuple[list[ExternalRecommendation], list[str]]:
        """Collect supported APIs independently so partial access remains useful."""
        recommendations: list[ExternalRecommendation] = []
        failed: list[str] = []
        calls = (
            ("ec2", "get_ec2_instance_recommendations", "instanceRecommendations"),
            ("ebs", "get_ebs_volume_recommendations", "volumeRecommendations"),
        )
        for label, operation, result_key in calls:
            try:
                rows = self._paginate(operation, result_key)
                normalizer = _normalize_compute_ec2 if label == "ec2" else _normalize_compute_ebs
                recommendations.extend(
                    item for row in rows if (item := normalizer(row, self._region)) is not None
                )
            except (ClientError, BotoCoreError, KeyError, TypeError, ValueError):
                failed.append(f"compute_optimizer_{label}")
        if len(failed) == len(calls):
            raise RecommendationProviderError(self.source, "COMPUTE_OPTIMIZER_UNAVAILABLE")
        return recommendations, failed

    def _paginate(self, operation: str, result_key: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        next_token: str | None = None
        method = getattr(self._client, operation)
        while True:
            request: dict[str, Any] = {"maxResults": 1000}
            if next_token:
                request["nextToken"] = next_token
            response = method(**request)
            rows.extend(response.get(result_key, []))
            next_token = response.get("nextToken")
            if not next_token:
                return rows


def _normalize_hub(raw: dict[str, Any]) -> ExternalRecommendation | None:
    resource_type = RESOURCE_TYPES.get(str(raw.get("currentResourceType", "")))
    action = ACTION_TYPES.get(str(raw.get("actionType", "")))
    resource_id = str(raw.get("resourceId") or raw.get("resourceArn") or "")
    recommendation_id = str(raw.get("recommendationId") or "")
    if not resource_type or not action or not resource_id or not recommendation_id:
        return None
    refreshed = _timestamp(raw.get("lastRefreshTimestamp"))
    return ExternalRecommendation(
        source=RecommendationSource.COST_OPTIMIZATION_HUB,
        source_recommendation_id=recommendation_id,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_arn=_optional_text(raw.get("resourceArn")),
        region=str(raw.get("region") or "global"),
        canonical_action=action,
        title=f"AWS recommends: {str(raw.get('actionType')).replace('Purchase', 'Purchase ')}",
        current_summary=str(raw.get("currentResourceSummary") or "Current AWS resource"),
        recommended_summary=str(
            raw.get("recommendedResourceSummary") or "Review AWS recommendation"
        ),
        current_monthly_cost=_decimal(raw.get("estimatedMonthlyCost")),
        estimated_monthly_savings=_decimal(raw.get("estimatedMonthlySavings")),
        currency=_optional_text(raw.get("currencyCode")),
        savings_percentage=_decimal(raw.get("estimatedSavingsPercentage")),
        implementation_effort=_optional_text(raw.get("implementationEffort")),
        restart_needed=_optional_bool(raw.get("restartNeeded")),
        rollback_possible=_optional_bool(raw.get("rollbackPossible")),
        lookback_days=_optional_int(raw.get("recommendationLookbackPeriodInDays")),
        last_refreshed_at=refreshed,
        confidence=_confidence(raw.get("implementationEffort"), None),
    )


def _normalize_compute_ec2(raw: dict[str, Any], region: str) -> ExternalRecommendation | None:
    if str(raw.get("finding", "")).lower() == "optimized":
        return None
    options = sorted(raw.get("recommendationOptions", []), key=lambda item: item.get("rank", 999))
    if not options or not raw.get("instanceArn"):
        return None
    option = options[0]
    savings, currency, percentage = _savings(option)
    if savings is None or savings <= 0:
        return None
    arn = str(raw["instanceArn"])
    resource_id = arn.rsplit("/", 1)[-1]
    recommended = str(option.get("instanceType") or "recommended instance type")
    return ExternalRecommendation(
        source=RecommendationSource.COMPUTE_OPTIMIZER,
        source_recommendation_id=f"{arn}:rightsize",
        resource_type="ec2_instance",
        resource_id=resource_id,
        resource_arn=arn,
        region=region,
        canonical_action="rightsize",
        title="Rightsize EC2 instance",
        current_summary=str(raw.get("currentInstanceType") or "Current instance type"),
        recommended_summary=recommended,
        current_monthly_cost=_current_from_savings(savings, percentage),
        estimated_monthly_savings=savings,
        currency=currency,
        savings_percentage=percentage,
        implementation_effort=_optional_text(option.get("migrationEffort")),
        restart_needed=True,
        rollback_possible=True,
        lookback_days=_optional_int(raw.get("lookBackPeriodInDays")),
        last_refreshed_at=_timestamp(raw.get("lastRefreshTimestamp")),
        confidence=_confidence(option.get("migrationEffort"), option.get("performanceRisk")),
    )


def _normalize_compute_ebs(raw: dict[str, Any], region: str) -> ExternalRecommendation | None:
    if str(raw.get("finding", "")).lower() == "optimized":
        return None
    options = sorted(
        raw.get("volumeRecommendationOptions", []), key=lambda item: item.get("rank", 999)
    )
    if not options or not raw.get("volumeArn"):
        return None
    option = options[0]
    savings, currency, percentage = _savings(option)
    if savings is None or savings <= 0:
        return None
    arn = str(raw["volumeArn"])
    resource_id = arn.rsplit("/", 1)[-1]
    current = raw.get("currentConfiguration") or {}
    recommended = option.get("configuration") or {}
    return ExternalRecommendation(
        source=RecommendationSource.COMPUTE_OPTIMIZER,
        source_recommendation_id=f"{arn}:rightsize",
        resource_type="ebs_volume",
        resource_id=resource_id,
        resource_arn=arn,
        region=region,
        canonical_action="rightsize",
        title="Rightsize EBS volume",
        current_summary=_configuration_summary(current),
        recommended_summary=_configuration_summary(recommended),
        current_monthly_cost=_current_from_savings(savings, percentage),
        estimated_monthly_savings=savings,
        currency=currency,
        savings_percentage=percentage,
        implementation_effort="Medium",
        restart_needed=False,
        rollback_possible=True,
        lookback_days=_optional_int(raw.get("lookBackPeriodInDays")),
        last_refreshed_at=_timestamp(raw.get("lastRefreshTimestamp")),
        confidence=_confidence("Medium", option.get("performanceRisk")),
    )


def _savings(option: dict[str, Any]) -> tuple[Decimal | None, str | None, Decimal | None]:
    opportunity = (
        option.get("savingsOpportunityAfterDiscounts") or option.get("savingsOpportunity") or {}
    )
    amount = opportunity.get("estimatedMonthlySavings") or {}
    return (
        _decimal(amount.get("value")),
        _optional_text(amount.get("currency")),
        _decimal(opportunity.get("savingsOpportunityPercentage")),
    )


def _current_from_savings(savings: Decimal | None, percentage: Decimal | None) -> Decimal | None:
    if savings is None or percentage is None or percentage <= 0:
        return None
    return savings / (percentage / Decimal("100"))


def _configuration_summary(value: dict[str, Any]) -> str:
    parts = [
        str(item)
        for item in (
            value.get("volumeType"),
            value.get("volumeSize"),
            value.get("volumeBaselineIOPS"),
        )
        if item is not None
    ]
    return " / ".join(parts) or "AWS volume configuration"


def _confidence(effort: object, performance_risk: object) -> Decimal:
    score = Decimal("0.85")
    if str(effort).lower() in {"high", "veryhigh"}:
        score -= Decimal("0.10")
    risk = _decimal(performance_risk)
    if risk is not None:
        score -= min(risk, Decimal("4")) * Decimal("0.05")
    return max(Decimal("0.50"), score)


def _timestamp(value: object) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(UTC)
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value, UTC)
    return datetime.now(UTC)


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    return Decimal(str(value))


def _optional_text(value: object) -> str | None:
    return str(value) if value not in {None, ""} else None


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _optional_int(value: object) -> int | None:
    return int(value) if isinstance(value, int | float) and not isinstance(value, bool) else None
