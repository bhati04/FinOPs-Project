"""Application service for AWS account identity and inventory."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cloudwise.aws_accounts.encryption import ExternalIdCipher
from cloudwise.aws_accounts.models import AWSAccountConnection, ConnectionStatus
from cloudwise.aws_accounts.provider import AWSProvider, AWSProviderError
from cloudwise.aws_accounts.schemas import (
    AWSIdentityResponse,
    ConnectionCreateRequest,
    ConnectionResponse,
    EC2InventoryResponse,
    EC2ResourceResponse,
)
from cloudwise.core.config import Settings


class AWSAccountService:
    """Provide AWS account information to the API layer."""

    def __init__(
        self,
        session: AsyncSession | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._cipher = (
            ExternalIdCipher(settings.external_id_encryption_key.get_secret_value())
            if settings
            else None
        )

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

    async def create_connection(
        self,
        organization_id: UUID,
        request: ConnectionCreateRequest,
    ) -> ConnectionResponse:
        """Persist a pending connection with a CloudWise-controlled External ID."""
        session, cipher = self._connection_dependencies()
        external_id = str(uuid4())
        connection = AWSAccountConnection(
            organization_id=organization_id,
            alias=request.alias.strip(),
            expected_account_id=request.expected_account_id,
            role_arn=request.role_arn,
            encrypted_external_id=cipher.encrypt(external_id),
            status=ConnectionStatus.PENDING,
            created_at=datetime.now(UTC),
            verified_at=None,
        )
        session.add(connection)
        await session.commit()
        return self._response(connection, external_id=external_id)

    async def list_connections(self, organization_id: UUID) -> list[ConnectionResponse]:
        """List only connections belonging to the authenticated organization."""
        session, _ = self._connection_dependencies()
        connections = (
            await session.scalars(
                select(AWSAccountConnection)
                .where(AWSAccountConnection.organization_id == organization_id)
                .order_by(AWSAccountConnection.created_at)
            )
        ).all()
        return [self._response(connection) for connection in connections]

    async def verify_connection(
        self,
        organization_id: UUID,
        connection_id: UUID,
        region: str,
    ) -> ConnectionResponse:
        """Assume and verify one organization-scoped customer role."""
        session, cipher = self._connection_dependencies()
        connection = await session.scalar(
            select(AWSAccountConnection).where(
                AWSAccountConnection.id == connection_id,
                AWSAccountConnection.organization_id == organization_id,
            )
        )
        if connection is None:
            raise LookupError("AWS account connection was not found")
        identity = AWSProvider.verify_assumable_role(
            connection.role_arn,
            cipher.decrypt(connection.encrypted_external_id),
            region,
        )
        if identity["account_id"] != connection.expected_account_id:
            connection.status = ConnectionStatus.FAILED
            await session.commit()
            raise AWSProviderError("Assumed role returned an unexpected AWS account")
        connection.status = ConnectionStatus.VERIFIED
        connection.verified_at = datetime.now(UTC)
        await session.commit()
        return self._response(connection)

    def _connection_dependencies(self) -> tuple[AsyncSession, ExternalIdCipher]:
        if self._session is None or self._cipher is None:
            raise RuntimeError("Connection persistence is not configured")
        return self._session, self._cipher

    @staticmethod
    def _response(
        connection: AWSAccountConnection,
        external_id: str | None = None,
    ) -> ConnectionResponse:
        return ConnectionResponse(
            id=connection.id,
            alias=connection.alias,
            expected_account_id=connection.expected_account_id,
            role_arn=connection.role_arn,
            status=connection.status,
            external_id=external_id,
            verified_at=connection.verified_at,
        )
