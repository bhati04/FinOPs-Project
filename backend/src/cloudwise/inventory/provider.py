"""Read-only, service-isolated AWS inventory collection."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypedDict

from botocore.exceptions import BotoCoreError, ClientError

from cloudwise.aws_accounts.provider import AWS_CLIENT_CONFIG, AWSProvider


class NormalizedResource(TypedDict):
    """Common resource shape persisted by inventory scans."""

    resource_type: str
    resource_id: str
    name: str
    state: str
    region: str
    details: dict[str, Any]


@dataclass(frozen=True)
class InventoryCollection:
    """Resources and safe service-level outcomes for one Region."""

    resources: list[NormalizedResource]
    completed_resource_types: frozenset[str]
    failed_services: tuple[str, ...]


class AWSInventoryProvider:
    """Collect supported resources using one assumed-role session."""

    def __init__(self, provider: AWSProvider) -> None:
        self._session = provider.session
        self._region = provider.region

    def collect(self) -> InventoryCollection:
        """Run collectors independently so access failures produce partial results."""
        collectors: tuple[
            tuple[str, frozenset[str], Callable[[], list[NormalizedResource]]], ...
        ] = (
            ("ec2", frozenset({"ec2_instance"}), self._ec2_instances),
            ("ebs", frozenset({"ebs_volume"}), self._ebs_volumes),
            ("snapshots", frozenset({"ebs_snapshot"}), self._ebs_snapshots),
            ("elastic_ips", frozenset({"elastic_ip"}), self._elastic_ips),
            ("nat", frozenset({"nat_gateway"}), self._nat_gateways),
            ("rds", frozenset({"rds_instance"}), self._rds_instances),
            ("lambda", frozenset({"lambda_function"}), self._lambda_functions),
            ("elb", frozenset({"load_balancer"}), self._load_balancers),
            ("ecs", frozenset({"ecs_cluster"}), self._ecs_clusters),
            ("eks", frozenset({"eks_cluster"}), self._eks_clusters),
            ("s3", frozenset({"s3_bucket"}), self._s3_buckets),
        )
        resources: list[NormalizedResource] = []
        completed_types: set[str] = set()
        failed_services: list[str] = []
        for service, resource_types, collector in collectors:
            try:
                resources.extend(collector())
                completed_types.update(resource_types)
            except (ClientError, BotoCoreError, KeyError, TypeError):
                failed_services.append(service)
        return InventoryCollection(
            resources=resources,
            completed_resource_types=frozenset(completed_types),
            failed_services=tuple(failed_services),
        )

    def _client(self, service: str) -> Any:
        return self._session.client(
            service,
            region_name=self._region,
            config=AWS_CLIENT_CONFIG,
        )

    @staticmethod
    def _tags(tags: list[dict[str, Any]] | None) -> dict[str, str]:
        return {
            str(tag["Key"]): str(tag["Value"])
            for tag in tags or []
            if "Key" in tag and "Value" in tag
        }

    @staticmethod
    def _json_value(value: object) -> object:
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    def _ec2_instances(self) -> list[NormalizedResource]:
        client = self._client("ec2")
        resources: list[NormalizedResource] = []
        for page in client.get_paginator("describe_instances").paginate():
            for reservation in page.get("Reservations", []):
                for instance in reservation.get("Instances", []):
                    tags = self._tags(instance.get("Tags"))
                    resources.append(
                        {
                            "resource_type": "ec2_instance",
                            "resource_id": instance["InstanceId"],
                            "name": tags.get("Name", "Unnamed"),
                            "state": instance["State"]["Name"],
                            "region": self._region,
                            "details": {
                                "instance_type": instance["InstanceType"],
                                "availability_zone": instance["Placement"]["AvailabilityZone"],
                                "private_ip": instance.get("PrivateIpAddress"),
                                "public_ip": instance.get("PublicIpAddress"),
                                "launch_time": self._json_value(instance["LaunchTime"]),
                                "tags": tags,
                            },
                        }
                    )
        return resources

    def _ebs_volumes(self) -> list[NormalizedResource]:
        client = self._client("ec2")
        resources: list[NormalizedResource] = []
        for page in client.get_paginator("describe_volumes").paginate():
            for volume in page.get("Volumes", []):
                tags = self._tags(volume.get("Tags"))
                resources.append(
                    {
                        "resource_type": "ebs_volume",
                        "resource_id": volume["VolumeId"],
                        "name": tags.get("Name", "Unnamed"),
                        "state": volume["State"],
                        "region": self._region,
                        "details": {
                            "availability_zone": volume["AvailabilityZone"],
                            "size_gib": volume["Size"],
                            "volume_type": volume["VolumeType"],
                            "encrypted": volume.get("Encrypted", False),
                            "iops": volume.get("Iops"),
                            "attachments": [
                                attachment.get("InstanceId")
                                for attachment in volume.get("Attachments", [])
                            ],
                            "tags": tags,
                        },
                    }
                )
        return resources

    def _ebs_snapshots(self) -> list[NormalizedResource]:
        client = self._client("ec2")
        resources: list[NormalizedResource] = []
        paginator = client.get_paginator("describe_snapshots")
        for page in paginator.paginate(OwnerIds=["self"]):
            for snapshot in page.get("Snapshots", []):
                tags = self._tags(snapshot.get("Tags"))
                resources.append(
                    {
                        "resource_type": "ebs_snapshot",
                        "resource_id": snapshot["SnapshotId"],
                        "name": tags.get("Name", snapshot.get("Description", "Unnamed")),
                        "state": snapshot["State"],
                        "region": self._region,
                        "details": {
                            "volume_id": snapshot.get("VolumeId"),
                            "volume_size_gib": snapshot.get("VolumeSize"),
                            "encrypted": snapshot.get("Encrypted", False),
                            "start_time": self._json_value(snapshot["StartTime"]),
                            "tags": tags,
                        },
                    }
                )
        return resources

    def _elastic_ips(self) -> list[NormalizedResource]:
        response = self._client("ec2").describe_addresses()
        resources: list[NormalizedResource] = []
        for address in response.get("Addresses", []):
            resources.append(
                {
                    "resource_type": "elastic_ip",
                    "resource_id": address.get("AllocationId", address["PublicIp"]),
                    "name": address["PublicIp"],
                    "state": ("associated" if address.get("AssociationId") else "unassociated"),
                    "region": self._region,
                    "details": {
                        "public_ip": address["PublicIp"],
                        "instance_id": address.get("InstanceId"),
                        "network_interface_id": address.get("NetworkInterfaceId"),
                        "domain": address.get("Domain"),
                        "tags": self._tags(address.get("Tags")),
                    },
                }
            )
        return resources

    def _nat_gateways(self) -> list[NormalizedResource]:
        client = self._client("ec2")
        resources: list[NormalizedResource] = []
        for page in client.get_paginator("describe_nat_gateways").paginate():
            for gateway in page.get("NatGateways", []):
                tags = self._tags(gateway.get("Tags"))
                resources.append(
                    {
                        "resource_type": "nat_gateway",
                        "resource_id": gateway["NatGatewayId"],
                        "name": tags.get("Name", "Unnamed"),
                        "state": gateway["State"],
                        "region": self._region,
                        "details": {
                            "subnet_id": gateway["SubnetId"],
                            "vpc_id": gateway["VpcId"],
                            "connectivity_type": gateway.get("ConnectivityType"),
                            "public_ips": [
                                item.get("PublicIp")
                                for item in gateway.get("NatGatewayAddresses", [])
                                if item.get("PublicIp")
                            ],
                            "tags": tags,
                        },
                    }
                )
        return resources

    def _rds_instances(self) -> list[NormalizedResource]:
        client = self._client("rds")
        resources: list[NormalizedResource] = []
        for page in client.get_paginator("describe_db_instances").paginate():
            for database in page.get("DBInstances", []):
                resources.append(
                    {
                        "resource_type": "rds_instance",
                        "resource_id": database["DBInstanceArn"],
                        "name": database["DBInstanceIdentifier"],
                        "state": database["DBInstanceStatus"],
                        "region": self._region,
                        "details": {
                            "engine": database["Engine"],
                            "engine_version": database.get("EngineVersion"),
                            "instance_class": database["DBInstanceClass"],
                            "storage_gib": database.get("AllocatedStorage"),
                            "multi_az": database.get("MultiAZ", False),
                            "encrypted": database.get("StorageEncrypted", False),
                        },
                    }
                )
        return resources

    def _lambda_functions(self) -> list[NormalizedResource]:
        client = self._client("lambda")
        resources: list[NormalizedResource] = []
        for page in client.get_paginator("list_functions").paginate():
            for function in page.get("Functions", []):
                resources.append(
                    {
                        "resource_type": "lambda_function",
                        "resource_id": function["FunctionArn"],
                        "name": function["FunctionName"],
                        "state": function.get("State", "active").lower(),
                        "region": self._region,
                        "details": {
                            "runtime": function.get("Runtime"),
                            "memory_mb": function["MemorySize"],
                            "timeout_seconds": function["Timeout"],
                            "code_size_bytes": function["CodeSize"],
                            "last_modified": function["LastModified"],
                        },
                    }
                )
        return resources

    def _load_balancers(self) -> list[NormalizedResource]:
        client = self._client("elbv2")
        resources: list[NormalizedResource] = []
        for page in client.get_paginator("describe_load_balancers").paginate():
            for balancer in page.get("LoadBalancers", []):
                resources.append(
                    {
                        "resource_type": "load_balancer",
                        "resource_id": balancer["LoadBalancerArn"],
                        "name": balancer["LoadBalancerName"],
                        "state": balancer["State"]["Code"],
                        "region": self._region,
                        "details": {
                            "type": balancer["Type"],
                            "scheme": balancer["Scheme"],
                            "vpc_id": balancer["VpcId"],
                            "availability_zones": [
                                zone["ZoneName"] for zone in balancer.get("AvailabilityZones", [])
                            ],
                        },
                    }
                )
        return resources

    def _ecs_clusters(self) -> list[NormalizedResource]:
        client = self._client("ecs")
        cluster_arns: list[str] = []
        for page in client.get_paginator("list_clusters").paginate():
            cluster_arns.extend(page.get("clusterArns", []))
        resources: list[NormalizedResource] = []
        for index in range(0, len(cluster_arns), 100):
            response = client.describe_clusters(
                clusters=cluster_arns[index : index + 100],
                include=["SETTINGS", "STATISTICS", "TAGS"],
            )
            for cluster in response.get("clusters", []):
                resources.append(
                    {
                        "resource_type": "ecs_cluster",
                        "resource_id": cluster["clusterArn"],
                        "name": cluster["clusterName"],
                        "state": cluster["status"].lower(),
                        "region": self._region,
                        "details": {
                            "running_tasks": cluster.get("runningTasksCount", 0),
                            "pending_tasks": cluster.get("pendingTasksCount", 0),
                            "registered_instances": cluster.get(
                                "registeredContainerInstancesCount", 0
                            ),
                            "tags": {
                                item["key"]: item["value"] for item in cluster.get("tags", [])
                            },
                        },
                    }
                )
        return resources

    def _eks_clusters(self) -> list[NormalizedResource]:
        client = self._client("eks")
        cluster_names: list[str] = []
        for page in client.get_paginator("list_clusters").paginate():
            cluster_names.extend(page.get("clusters", []))
        resources: list[NormalizedResource] = []
        for cluster_name in cluster_names:
            cluster = client.describe_cluster(name=cluster_name)["cluster"]
            resources.append(
                {
                    "resource_type": "eks_cluster",
                    "resource_id": cluster["arn"],
                    "name": cluster["name"],
                    "state": cluster["status"].lower(),
                    "region": self._region,
                    "details": {
                        "version": cluster["version"],
                        "endpoint_public_access": cluster.get("resourcesVpcConfig", {}).get(
                            "endpointPublicAccess"
                        ),
                        "platform_version": cluster.get("platformVersion"),
                        "tags": cluster.get("tags", {}),
                    },
                }
            )
        return resources

    def _s3_buckets(self) -> list[NormalizedResource]:
        client = self._client("s3")
        resources: list[NormalizedResource] = []
        for bucket in client.list_buckets().get("Buckets", []):
            location = client.get_bucket_location(Bucket=bucket["Name"]).get("LocationConstraint")
            bucket_region = "us-east-1" if location in {None, ""} else location
            if bucket_region != self._region:
                continue
            resources.append(
                {
                    "resource_type": "s3_bucket",
                    "resource_id": bucket["Name"],
                    "name": bucket["Name"],
                    "state": "available",
                    "region": bucket_region,
                    "details": {
                        "creation_date": self._json_value(bucket["CreationDate"]),
                    },
                }
            )
        return resources
