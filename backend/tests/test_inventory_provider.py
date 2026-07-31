"""Real inventory provider orchestration tests."""

from unittest.mock import MagicMock

from botocore.exceptions import ClientError

from cloudwise.inventory.provider import AWSInventoryProvider


def test_service_failure_produces_partial_collection() -> None:
    """One denied AWS service must not discard successful service results."""
    assumed_provider = MagicMock()
    assumed_provider.region = "us-east-1"
    provider = AWSInventoryProvider(assumed_provider)
    provider._ec2_instances = MagicMock(  # type: ignore[method-assign]
        return_value=[
            {
                "resource_type": "ec2_instance",
                "resource_id": "i-example",
                "name": "web",
                "state": "running",
                "region": "us-east-1",
                "details": {},
            }
        ]
    )
    provider._ebs_volumes = MagicMock(  # type: ignore[method-assign]
        side_effect=ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "denied"}},
            "DescribeVolumes",
        )
    )
    for collector_name in (
        "_ebs_snapshots",
        "_elastic_ips",
        "_nat_gateways",
        "_rds_instances",
        "_lambda_functions",
        "_load_balancers",
        "_ecs_clusters",
        "_eks_clusters",
        "_s3_buckets",
    ):
        setattr(provider, collector_name, MagicMock(return_value=[]))

    result = provider.collect()

    assert len(result.resources) == 1
    assert "ec2_instance" in result.completed_resource_types
    assert "ebs" in result.failed_services
