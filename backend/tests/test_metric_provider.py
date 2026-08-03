"""CloudWatch metric batching and normalization tests."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

from cloudwise.metrics.provider import AWSMetricProvider, MetricResource


def test_metric_provider_normalizes_resource_datapoints() -> None:
    """Metric query context is retained without exposing resource IDs in labels."""
    timestamp = datetime(2026, 8, 3, 4, tzinfo=UTC)
    client = MagicMock()
    client.get_metric_data.return_value = {
        "MetricDataResults": [
            {
                "Id": "m0",
                "Timestamps": [timestamp],
                "Values": [12.5],
                "StatusCode": "Complete",
            }
        ]
    }
    assumed_provider = MagicMock()
    assumed_provider.region = "us-east-1"
    assumed_provider.session.client.return_value = client
    resource_id = uuid4()

    collection = AWSMetricProvider(assumed_provider).get_metrics(
        [MetricResource(resource_id, "ec2_instance", "i-example", "worker")],
        timestamp - timedelta(days=7),
        timestamp,
    )

    assert collection.query_count == 3
    assert collection.failed_batch_count == 0
    assert collection.records[0]["inventory_resource_id"] == resource_id
    assert collection.records[0]["metric_name"] == "CPUUtilization"
    assert str(collection.records[0]["value"]) == "12.5"
    queries = client.get_metric_data.call_args.kwargs["MetricDataQueries"]
    assert queries[0]["MetricStat"]["Metric"]["Dimensions"] == [
        {"Name": "InstanceId", "Value": "i-example"}
    ]


def test_metric_provider_batches_at_cloudwatch_limit() -> None:
    """GetMetricData requests never exceed the 500-query service limit."""
    client = MagicMock()
    client.get_metric_data.return_value = {"MetricDataResults": []}
    assumed_provider = MagicMock()
    assumed_provider.region = "us-east-1"
    assumed_provider.session.client.return_value = client
    resources = [
        MetricResource(uuid4(), "ec2_instance", f"i-{index}", f"instance-{index}")
        for index in range(167)
    ]
    end = datetime(2026, 8, 3, tzinfo=UTC)

    collection = AWSMetricProvider(assumed_provider).get_metrics(
        resources,
        end - timedelta(days=7),
        end,
    )

    assert collection.query_count == 501
    assert client.get_metric_data.call_count == 2
    assert len(client.get_metric_data.call_args_list[0].kwargs["MetricDataQueries"]) == 500
    assert len(client.get_metric_data.call_args_list[1].kwargs["MetricDataQueries"]) == 1


def test_application_load_balancer_uses_arn_suffix_dimension() -> None:
    """ApplicationELB expects the ARN suffix rather than the full ARN."""
    client = MagicMock()
    client.get_metric_data.return_value = {"MetricDataResults": []}
    assumed_provider = MagicMock()
    assumed_provider.region = "us-east-1"
    assumed_provider.session.client.return_value = client
    resource = MetricResource(
        uuid4(),
        "load_balancer",
        "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/web/abc",
        "web",
    )
    end = datetime(2026, 8, 3, tzinfo=UTC)

    AWSMetricProvider(assumed_provider).get_metrics(
        [resource],
        end - timedelta(days=7),
        end,
    )

    queries = client.get_metric_data.call_args.kwargs["MetricDataQueries"]
    assert queries[0]["MetricStat"]["Metric"]["Dimensions"][0]["Value"] == "app/web/abc"
