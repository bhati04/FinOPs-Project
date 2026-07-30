"""Application service for AWS account identity and inventory."""

from cloudwise.aws_accounts.provider import AWSProvider
from cloudwise.aws_accounts.schemas import (
    AWSIdentityResponse,
    EC2InventoryResponse,
    EC2ResourceResponse,
)


class AWSAccountService:
    """Provide AWS account information to the API layer."""

    def get_identity(self, region: str) -> AWSIdentityResponse:
        """Verify and return the current AWS identity."""

        provider = AWSProvider(region=region)
        identity = provider.get_identity()

        return AWSIdentityResponse(
            account_id=identity["account_id"],
            principal_arn=identity["principal_arn"],
            principal_id=identity["principal_id"],
            authentication_type="ec2_instance_role",
            region=region,
            status="verified",
        )

    def get_ec2_inventory(self, region: str) -> EC2InventoryResponse:
        """Return normalized EC2 inventory for one Region."""

        provider = AWSProvider(region=region)

        identity = provider.get_identity()
        resources = provider.list_ec2_instances()

        normalized_resources = [EC2ResourceResponse(**resource) for resource in resources]

        return EC2InventoryResponse(
            account_id=identity["account_id"],
            region=region,
            resource_count=len(normalized_resources),
            resources=normalized_resources,
        )


def get_aws_account_service() -> AWSAccountService:
    """FastAPI dependency provider for AWS account operations."""

    return AWSAccountService()
