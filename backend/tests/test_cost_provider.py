"""Cost Explorer normalization tests."""

from datetime import date, timedelta
from unittest.mock import MagicMock

from cloudwise.cost_management.models import CostGranularity, CostGrouping
from cloudwise.cost_management.provider import AWSCostProvider
from cloudwise.cost_management.tasks import _forecast_windows


def test_forecast_windows_start_on_current_date() -> None:
    """Cost Explorer rejects a forecast whose start is later than today."""
    today = date(2026, 8, 3)

    windows = _forecast_windows(today)

    assert all(start == today for _, start, _ in windows)
    assert windows[0][2] == today + timedelta(days=30)
    assert windows[1][2] == today + timedelta(days=90)


def test_cost_provider_normalizes_grouped_amounts() -> None:
    """Provider preserves currency and grouping dimensions."""
    client = MagicMock()
    client.get_cost_and_usage.return_value = {
        "ResultsByTime": [
            {
                "TimePeriod": {"Start": "2026-07-01", "End": "2026-07-02"},
                "Groups": [
                    {
                        "Keys": ["Amazon Elastic Compute Cloud - Compute", "us-east-1"],
                        "Metrics": {
                            "UnblendedCost": {"Amount": "1.25000000", "Unit": "USD"}
                        },
                    }
                ],
            }
        ]
    }
    assumed_provider = MagicMock()
    assumed_provider.session.client.return_value = client
    provider = AWSCostProvider(assumed_provider)

    records = provider.get_costs(
        date(2026, 7, 1),
        date(2026, 7, 2),
        CostGranularity.DAILY,
        CostGrouping.SERVICE_REGION,
    )

    assert len(records) == 1
    assert str(records[0]["amount"]) == "1.25000000"
    assert records[0]["currency"] == "USD"
    assert records[0]["region"] == "us-east-1"
    assert records[0]["service"] == "Amazon Elastic Compute Cloud - Compute"


def test_cost_provider_paginates_usage_type_groups() -> None:
    """Every Cost Explorer page is normalized for the requested grouping."""
    client = MagicMock()
    client.get_cost_and_usage.side_effect = [
        {
            "ResultsByTime": [],
            "NextPageToken": "next-page",
        },
        {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2026-07-01", "End": "2026-07-02"},
                    "Groups": [
                        {
                            "Keys": ["BoxUsage:t3.micro"],
                            "Metrics": {
                                "UnblendedCost": {"Amount": "0.42", "Unit": "USD"}
                            },
                        }
                    ],
                }
            ]
        },
    ]
    assumed_provider = MagicMock()
    assumed_provider.session.client.return_value = client

    records = AWSCostProvider(assumed_provider).get_costs(
        date(2026, 7, 1),
        date(2026, 7, 2),
        CostGranularity.DAILY,
        CostGrouping.USAGE_TYPE,
    )

    assert records[0]["usage_type"] == "BoxUsage:t3.micro"
    assert records[0]["service"] == ""
    assert client.get_cost_and_usage.call_count == 2
    assert client.get_cost_and_usage.call_args.kwargs["NextPageToken"] == "next-page"


def test_cost_provider_normalizes_configured_tag_values() -> None:
    """Cost allocation tag responses retain the configured key and safe value."""
    client = MagicMock()
    client.get_cost_and_usage.return_value = {
        "ResultsByTime": [
            {
                "TimePeriod": {"Start": "2026-07-01", "End": "2026-07-02"},
                "Groups": [
                    {
                        "Keys": ["Environment$production"],
                        "Metrics": {
                            "UnblendedCost": {"Amount": "8.00", "Unit": "USD"}
                        },
                    }
                ],
            }
        ]
    }
    assumed_provider = MagicMock()
    assumed_provider.session.client.return_value = client

    records = AWSCostProvider(assumed_provider).get_costs(
        date(2026, 7, 1),
        date(2026, 7, 2),
        CostGranularity.DAILY,
        CostGrouping.TAG,
        tag_key="Environment",
    )

    assert records[0]["tag_key"] == "Environment"
    assert records[0]["tag_value"] == "production"


def test_cost_provider_normalizes_forecast_bounds() -> None:
    """Forecast means and prediction bounds remain decimal values."""
    client = MagicMock()
    client.get_cost_forecast.return_value = {
        "Total": {"Amount": "12.00", "Unit": "USD"},
        "ForecastResultsByTime": [
            {
                "TimePeriod": {"Start": "2026-08-04", "End": "2026-08-05"},
                "MeanValue": "1.25",
                "PredictionIntervalLowerBound": "0.90",
                "PredictionIntervalUpperBound": "1.70",
            }
        ],
    }
    assumed_provider = MagicMock()
    assumed_provider.session.client.return_value = client

    forecasts = AWSCostProvider(assumed_provider).get_forecast(
        date(2026, 8, 4),
        date(2026, 8, 5),
        CostGranularity.DAILY,
    )

    assert str(forecasts[0]["mean_amount"]) == "1.25"
    assert str(forecasts[0]["lower_bound"]) == "0.90"
    assert forecasts[0]["currency"] == "USD"
