"""AWS Cost Explorer provider."""

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, TypedDict

from botocore.exceptions import BotoCoreError, ClientError

from cloudwise.aws_accounts.provider import AWS_CLIENT_CONFIG, AWSProvider
from cloudwise.cost_management.models import CostGranularity, CostGrouping


class CostRecord(TypedDict):
    """Normalized Cost Explorer group."""

    granularity: CostGranularity
    period_start: date
    grouping: CostGrouping
    service: str
    region: str
    usage_type: str
    tag_key: str
    tag_value: str
    amount: Decimal
    currency: str


class CostForecastRecord(TypedDict):
    """Normalized Cost Explorer forecast period."""

    granularity: CostGranularity
    period_start: date
    period_end: date
    mean_amount: Decimal
    lower_bound: Decimal
    upper_bound: Decimal
    currency: str


class CostProviderError(RuntimeError):
    """Raised when Cost Explorer cannot be synchronized."""


class AWSCostProvider:
    """Read grouped UnblendedCost through an assumed-role session."""

    def __init__(self, provider: AWSProvider) -> None:
        self._client: Any = provider.session.client(
            "ce",
            region_name="us-east-1",
            config=AWS_CLIENT_CONFIG,
        )

    def get_costs(
        self,
        start: date,
        end: date,
        granularity: CostGranularity,
        grouping: CostGrouping,
        *,
        tag_key: str | None = None,
    ) -> list[CostRecord]:
        """Return paginated aggregates for one supported grouping view."""
        group_by = self._group_by(grouping, tag_key)
        request: dict[str, Any] = {
            "TimePeriod": {"Start": start.isoformat(), "End": end.isoformat()},
            "Granularity": granularity.value.upper(),
            "Metrics": ["UnblendedCost"],
            "GroupBy": group_by,
        }
        records: list[CostRecord] = []
        try:
            while True:
                response = self._client.get_cost_and_usage(**request)
                for period in response.get("ResultsByTime", []):
                    period_start = date.fromisoformat(period["TimePeriod"]["Start"])
                    for group in period.get("Groups", []):
                        metric = group["Metrics"]["UnblendedCost"]
                        keys = group.get("Keys", [])
                        dimensions = self._dimensions(grouping, keys, tag_key)
                        records.append(
                            {
                                "granularity": granularity,
                                "period_start": period_start,
                                "grouping": grouping,
                                "amount": Decimal(metric["Amount"]),
                                "currency": metric["Unit"],
                                **dimensions,
                            }
                        )
                token = response.get("NextPageToken")
                if not token:
                    break
                request["NextPageToken"] = token
            return records
        except (ClientError, BotoCoreError, InvalidOperation, KeyError, ValueError) as exc:
            raise CostProviderError("Cost Explorer synchronization failed") from exc

    def get_forecast(
        self,
        start: date,
        end: date,
        granularity: CostGranularity,
    ) -> list[CostForecastRecord]:
        """Return normalized UnblendedCost forecast periods."""
        try:
            response = self._client.get_cost_forecast(
                TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
                Metric="UNBLENDED_COST",
                Granularity=granularity.value.upper(),
                PredictionIntervalLevel=80,
            )
            currency = response["Total"]["Unit"]
            return [
                {
                    "granularity": granularity,
                    "period_start": date.fromisoformat(item["TimePeriod"]["Start"]),
                    "period_end": date.fromisoformat(item["TimePeriod"]["End"]),
                    "mean_amount": Decimal(item["MeanValue"]),
                    "lower_bound": Decimal(item["PredictionIntervalLowerBound"]),
                    "upper_bound": Decimal(item["PredictionIntervalUpperBound"]),
                    "currency": currency,
                }
                for item in response.get("ForecastResultsByTime", [])
            ]
        except (ClientError, BotoCoreError, InvalidOperation, KeyError, ValueError) as exc:
            raise CostProviderError("Cost Explorer forecast failed") from exc

    @staticmethod
    def _group_by(grouping: CostGrouping, tag_key: str | None) -> list[dict[str, str]]:
        if grouping is CostGrouping.SERVICE_REGION:
            return [
                {"Type": "DIMENSION", "Key": "SERVICE"},
                {"Type": "DIMENSION", "Key": "REGION"},
            ]
        if grouping is CostGrouping.USAGE_TYPE:
            return [{"Type": "DIMENSION", "Key": "USAGE_TYPE"}]
        if not tag_key:
            raise ValueError("A cost allocation tag key is required for tag grouping")
        return [{"Type": "TAG", "Key": tag_key}]

    @staticmethod
    def _dimensions(
        grouping: CostGrouping,
        keys: list[str],
        tag_key: str | None,
    ) -> dict[str, str]:
        dimensions = {
            "service": "",
            "region": "",
            "usage_type": "",
            "tag_key": "",
            "tag_value": "",
        }
        if grouping is CostGrouping.SERVICE_REGION:
            dimensions["service"] = keys[0] if keys else "Unknown"
            dimensions["region"] = keys[1] if len(keys) > 1 else "global"
        elif grouping is CostGrouping.USAGE_TYPE:
            dimensions["usage_type"] = keys[0] if keys else "Unknown"
        else:
            normalized_key = tag_key or ""
            value = keys[0] if keys else ""
            prefix = f"{normalized_key}$"
            dimensions["tag_key"] = normalized_key
            dimensions["tag_value"] = value.removeprefix(prefix) or "Untagged"
        return dimensions
