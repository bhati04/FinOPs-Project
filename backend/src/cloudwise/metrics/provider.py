"""Batched AWS CloudWatch metric provider."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, TypedDict
from uuid import UUID

from botocore.exceptions import BotoCoreError, ClientError

from cloudwise.aws_accounts.provider import AWS_CLIENT_CONFIG, AWSProvider


@dataclass(frozen=True)
class MetricResource:
    """Inventory resource fields needed to construct CloudWatch dimensions."""

    id: UUID
    resource_type: str
    resource_id: str
    name: str


@dataclass(frozen=True)
class MetricDefinition:
    """Supported CloudWatch metric contract."""

    namespace: str
    metric_name: str
    statistic: str
    unit: str
    dimension_name: str
    dimension_source: str


class MetricRecord(TypedDict):
    """Normalized CloudWatch datapoint."""

    inventory_resource_id: UUID
    namespace: str
    metric_name: str
    statistic: str
    unit: str
    timestamp: datetime
    value: Decimal


@dataclass(frozen=True)
class MetricCollection:
    """Normalized records and safe batch-level failure count."""

    records: list[MetricRecord]
    failed_batch_count: int
    query_count: int


RESOURCE_METRICS: dict[str, tuple[MetricDefinition, ...]] = {
    "ec2_instance": (
        MetricDefinition("AWS/EC2", "CPUUtilization", "Average", "Percent", "InstanceId", "id"),
        MetricDefinition("AWS/EC2", "NetworkIn", "Sum", "Bytes", "InstanceId", "id"),
        MetricDefinition("AWS/EC2", "NetworkOut", "Sum", "Bytes", "InstanceId", "id"),
    ),
    "ebs_volume": (
        MetricDefinition("AWS/EBS", "VolumeReadOps", "Sum", "Count", "VolumeId", "id"),
        MetricDefinition("AWS/EBS", "VolumeWriteOps", "Sum", "Count", "VolumeId", "id"),
        MetricDefinition("AWS/EBS", "VolumeIdleTime", "Sum", "Seconds", "VolumeId", "id"),
    ),
    "nat_gateway": (
        MetricDefinition(
            "AWS/NATGateway",
            "ActiveConnectionCount",
            "Average",
            "Count",
            "NatGatewayId",
            "id",
        ),
        MetricDefinition(
            "AWS/NATGateway",
            "BytesInFromSource",
            "Sum",
            "Bytes",
            "NatGatewayId",
            "id",
        ),
        MetricDefinition(
            "AWS/NATGateway",
            "BytesOutToDestination",
            "Sum",
            "Bytes",
            "NatGatewayId",
            "id",
        ),
    ),
    "rds_instance": (
        MetricDefinition(
            "AWS/RDS", "CPUUtilization", "Average", "Percent", "DBInstanceIdentifier", "name"
        ),
        MetricDefinition(
            "AWS/RDS",
            "DatabaseConnections",
            "Average",
            "Count",
            "DBInstanceIdentifier",
            "name",
        ),
        MetricDefinition(
            "AWS/RDS", "FreeStorageSpace", "Average", "Bytes", "DBInstanceIdentifier", "name"
        ),
    ),
    "lambda_function": (
        MetricDefinition("AWS/Lambda", "Invocations", "Sum", "Count", "FunctionName", "name"),
        MetricDefinition("AWS/Lambda", "Errors", "Sum", "Count", "FunctionName", "name"),
        MetricDefinition(
            "AWS/Lambda", "Duration", "Average", "Milliseconds", "FunctionName", "name"
        ),
    ),
    "load_balancer": (
        MetricDefinition(
            "AWS/ApplicationELB", "RequestCount", "Sum", "Count", "LoadBalancer", "alb_suffix"
        ),
        MetricDefinition(
            "AWS/ApplicationELB",
            "TargetResponseTime",
            "Average",
            "Seconds",
            "LoadBalancer",
            "alb_suffix",
        ),
        MetricDefinition(
            "AWS/ApplicationELB",
            "HTTPCode_Target_5XX_Count",
            "Sum",
            "Count",
            "LoadBalancer",
            "alb_suffix",
        ),
    ),
}


class AWSMetricProvider:
    """Read supported resource metrics through one assumed-role session."""

    def __init__(self, provider: AWSProvider) -> None:
        self._client: Any = provider.session.client(
            "cloudwatch",
            region_name=provider.region,
            config=AWS_CLIENT_CONFIG,
        )

    def get_metrics(
        self,
        resources: list[MetricResource],
        start: datetime,
        end: datetime,
        *,
        period_seconds: int = 3600,
    ) -> MetricCollection:
        """Fetch up to 500 MetricDataQuery entries per request with pagination."""
        queries: list[dict[str, Any]] = []
        query_context: dict[str, tuple[MetricResource, MetricDefinition]] = {}
        for resource in resources:
            for definition in RESOURCE_METRICS.get(resource.resource_type, ()):
                query_id = f"m{len(queries)}"
                queries.append(
                    {
                        "Id": query_id,
                        "MetricStat": {
                            "Metric": {
                                "Namespace": definition.namespace,
                                "MetricName": definition.metric_name,
                                "Dimensions": [
                                    {
                                        "Name": definition.dimension_name,
                                        "Value": self._dimension_value(resource, definition),
                                    }
                                ],
                            },
                            "Period": period_seconds,
                            "Stat": definition.statistic,
                        },
                        "ReturnData": True,
                    }
                )
                query_context[query_id] = (resource, definition)

        records: list[MetricRecord] = []
        failed_batches = 0
        for offset in range(0, len(queries), 500):
            batch = queries[offset : offset + 500]
            request: dict[str, Any] = {
                "MetricDataQueries": batch,
                "StartTime": start,
                "EndTime": end,
                "ScanBy": "TimestampAscending",
            }
            try:
                while True:
                    response = self._client.get_metric_data(**request)
                    for result in response.get("MetricDataResults", []):
                        context = query_context.get(result.get("Id", ""))
                        if context is None:
                            continue
                        resource, definition = context
                        for timestamp, value in zip(
                            result.get("Timestamps", []),
                            result.get("Values", []),
                            strict=True,
                        ):
                            records.append(
                                {
                                    "inventory_resource_id": resource.id,
                                    "namespace": definition.namespace,
                                    "metric_name": definition.metric_name,
                                    "statistic": definition.statistic,
                                    "unit": definition.unit,
                                    "timestamp": timestamp,
                                    "value": Decimal(str(value)),
                                }
                            )
                    token = response.get("NextToken")
                    if not token:
                        break
                    request["NextToken"] = token
            except (ClientError, BotoCoreError, ValueError, TypeError):
                failed_batches += 1
        return MetricCollection(records, failed_batches, len(queries))

    @staticmethod
    def _dimension_value(
        resource: MetricResource,
        definition: MetricDefinition,
    ) -> str:
        if definition.dimension_source == "name":
            return resource.name
        if definition.dimension_source == "alb_suffix":
            marker = ":loadbalancer/"
            return resource.resource_id.split(marker, 1)[-1]
        return resource.resource_id
