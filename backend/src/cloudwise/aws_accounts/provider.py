"""AWS SDK provider for account identity and EC2 inventory."""

from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

AWS_CLIENT_CONFIG = Config(
    retries={
        "max_attempts": 5,
        "mode": "standard",
    },
    connect_timeout=5,
    read_timeout=20,
    user_agent_extra="CloudWise/0.1",
)


class AWSProviderError(RuntimeError):
    """Raised when an AWS API operation cannot be completed."""


class AWSProvider:
    """Access AWS using the default Boto3 credential chain."""

    def __init__(self, region: str) -> None:
        self.region = region
        self.session = boto3.Session(region_name=region)

    def get_identity(self) -> dict[str, str]:
        """Return the current AWS account and principal identity."""

        try:
            sts_client = self.session.client(
                "sts",
                config=AWS_CLIENT_CONFIG,
            )

            response = sts_client.get_caller_identity()

            return {
                "account_id": response["Account"],
                "principal_arn": response["Arn"],
                "principal_id": response["UserId"],
            }

        except (ClientError, BotoCoreError) as exc:
            raise AWSProviderError("Unable to retrieve AWS account identity") from exc

    def list_ec2_instances(self) -> list[dict[str, Any]]:
        """Return normalized EC2 instances from the selected Region."""

        try:
            ec2_client = self.session.client(
                "ec2",
                region_name=self.region,
                config=AWS_CLIENT_CONFIG,
            )

            paginator = ec2_client.get_paginator("describe_instances")
            resources: list[dict[str, Any]] = []

            for page in paginator.paginate():
                for reservation in page.get("Reservations", []):
                    for instance in reservation.get("Instances", []):
                        tags = {tag["Key"]: tag["Value"] for tag in instance.get("Tags", [])}

                        resources.append(
                            {
                                "resource_id": instance["InstanceId"],
                                "name": tags.get("Name", "Unnamed"),
                                "instance_type": instance["InstanceType"],
                                "state": instance["State"]["Name"],
                                "availability_zone": instance["Placement"]["AvailabilityZone"],
                                "private_ip": instance.get("PrivateIpAddress"),
                                "public_ip": instance.get("PublicIpAddress"),
                                "launch_time": instance["LaunchTime"],
                                "tags": tags,
                            }
                        )

            return resources

        except (ClientError, BotoCoreError) as exc:
            raise AWSProviderError(
                f"Unable to retrieve EC2 inventory from Region {self.region}"
            ) from exc

    @staticmethod
    def verify_assumable_role(
        role_arn: str,
        external_id: str,
        region: str,
    ) -> dict[str, str]:
        """Assume a customer role and return its verified identity."""
        try:
            sts = boto3.client("sts", region_name=region, config=AWS_CLIENT_CONFIG)
            assumed = sts.assume_role(
                RoleArn=role_arn,
                RoleSessionName="cloudwise-verification",
                ExternalId=external_id,
                DurationSeconds=900,
            )
            credentials = assumed["Credentials"]
            customer_sts = boto3.client(
                "sts",
                region_name=region,
                aws_access_key_id=credentials["AccessKeyId"],
                aws_secret_access_key=credentials["SecretAccessKey"],
                aws_session_token=credentials["SessionToken"],
                config=AWS_CLIENT_CONFIG,
            )
            identity = customer_sts.get_caller_identity()
            return {"account_id": identity["Account"], "arn": identity["Arn"]}
        except (ClientError, BotoCoreError, KeyError) as exc:
            raise AWSProviderError("Unable to verify the customer AWS role") from exc
