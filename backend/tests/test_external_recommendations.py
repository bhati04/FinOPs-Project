"""AWS recommendation normalization and source boundary tests."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

from cloudwise.recommendations.external import (
    AWSComputeOptimizerProvider,
    AWSCostOptimizationHubProvider,
)


def test_cost_optimization_hub_requests_aws_deduplication() -> None:
    """The primary source requests one AWS-deduplicated result per resource."""
    client = MagicMock()
    client.list_recommendations.return_value = {
        "items": [
            {
                "accountId": "123456789012",
                "actionType": "Rightsize",
                "currencyCode": "USD",
                "currentResourceSummary": "m6i.large",
                "currentResourceType": "Ec2Instance",
                "estimatedMonthlyCost": 100,
                "estimatedMonthlySavings": 30,
                "estimatedSavingsPercentage": 30,
                "implementationEffort": "Low",
                "lastRefreshTimestamp": datetime(2026, 8, 4, tzinfo=UTC),
                "recommendationId": "temporary-aws-id",
                "recommendationLookbackPeriodInDays": 14,
                "recommendedResourceSummary": "m6i.medium",
                "region": "us-east-1",
                "resourceArn": "arn:aws:ec2:us-east-1:123456789012:instance/i-example",
                "resourceId": "i-example",
                "restartNeeded": True,
                "rollbackPossible": True,
            }
        ]
    }
    provider = MagicMock()
    provider.session.client.return_value = client

    results = AWSCostOptimizationHubProvider(provider).collect("123456789012")

    assert client.list_recommendations.call_args.kwargs["includeAllRecommendations"] is False
    assert results[0].canonical_action == "rightsize"
    assert results[0].estimated_monthly_savings == Decimal("30")


def test_compute_optimizer_keeps_successful_resource_family() -> None:
    """An EBS API failure does not discard valid EC2 fallback results."""
    client = MagicMock()
    client.get_ec2_instance_recommendations.return_value = {
        "instanceRecommendations": [
            {
                "finding": "Overprovisioned",
                "instanceArn": "arn:aws:ec2:us-east-1:123456789012:instance/i-example",
                "currentInstanceType": "m6i.large",
                "lastRefreshTimestamp": datetime(2026, 8, 4, tzinfo=UTC),
                "lookBackPeriodInDays": 14,
                "recommendationOptions": [
                    {
                        "rank": 1,
                        "instanceType": "m6i.medium",
                        "migrationEffort": "Low",
                        "performanceRisk": 1,
                        "savingsOpportunity": {
                            "estimatedMonthlySavings": {"currency": "USD", "value": 25},
                            "savingsOpportunityPercentage": 25,
                        },
                    }
                ],
            }
        ]
    }
    client.get_ebs_volume_recommendations.side_effect = ValueError("invalid response")
    provider = MagicMock(region="us-east-1")
    provider.session.client.return_value = client

    results, failed = AWSComputeOptimizerProvider(provider).collect()

    assert len(results) == 1
    assert results[0].current_monthly_cost == Decimal("100")
    assert failed == ["compute_optimizer_ebs"]
