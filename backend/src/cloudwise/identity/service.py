"""Identity registration, authentication, and session rotation."""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from cloudwise.core.config import Settings
from cloudwise.identity.models import RefreshSession, User
from cloudwise.identity.schemas import RegisterRequest, TokenResponse
from cloudwise.identity.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from cloudwise.organizations.models import (
    Organization,
    OrganizationMembership,
    OrganizationRole,
)


class AuthenticationError(ValueError):
    """Generic authentication failure safe for API translation."""


class RegistrationConflictError(ValueError):
    """Registration conflicts with an existing identity."""


@dataclass(frozen=True)
class AuthenticatedUser:
    """Validated user and tenant context."""

    user_id: UUID
    email: str
    organization_id: UUID
    organization_name: str
    role: OrganizationRole


class IdentityService:
    """Coordinate identity persistence and token issuance."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def register(self, request: RegisterRequest) -> TokenResponse:
        """Create a user, its initial organization, and owner membership."""
        now = datetime.now(UTC)
        password_digest = await asyncio.to_thread(hash_password, request.password)
        user = User(
            email=request.email,
            password_hash=password_digest,
            is_active=True,
            created_at=now,
        )
        organization = Organization(name=request.organization_name.strip(), created_at=now)
        self._session.add_all([user, organization])
        try:
            await self._session.flush()
            membership = OrganizationMembership(
                organization_id=organization.id,
                user_id=user.id,
                role=OrganizationRole.OWNER,
                created_at=now,
            )
            self._session.add(membership)
            tokens = self._issue_tokens(user.id, organization.id, membership.role, now)
            await self._session.commit()
            return tokens
        except IntegrityError as exc:
            await self._session.rollback()
            raise RegistrationConflictError("Registration could not be completed") from exc

    async def login(self, email: str, password: str) -> TokenResponse:
        """Authenticate without revealing whether an email exists."""
        user = await self._session.scalar(
            select(User).where(User.email == email.strip().lower(), User.is_active.is_(True))
        )
        if user is None or not await asyncio.to_thread(
            verify_password,
            password,
            user.password_hash,
        ):
            raise AuthenticationError("Invalid credentials")
        membership = await self._session.scalar(
            select(OrganizationMembership)
            .where(OrganizationMembership.user_id == user.id)
            .order_by(OrganizationMembership.created_at)
        )
        if membership is None:
            raise AuthenticationError("Invalid credentials")
        tokens = self._issue_tokens(
            user.id,
            membership.organization_id,
            membership.role,
            datetime.now(UTC),
        )
        await self._session.commit()
        return tokens

    async def refresh(self, token: str) -> TokenResponse:
        """Rotate a valid refresh session and revoke the previous token."""
        now = datetime.now(UTC)
        session = await self._session.scalar(
            select(RefreshSession).where(
                RefreshSession.token_hash == hash_refresh_token(token),
                RefreshSession.revoked_at.is_(None),
                RefreshSession.expires_at > now,
            )
        )
        if session is None:
            raise AuthenticationError("Invalid refresh token")
        user = await self._session.get(User, session.user_id)
        membership = await self._session.scalar(
            select(OrganizationMembership).where(
                OrganizationMembership.user_id == session.user_id,
                OrganizationMembership.organization_id == session.organization_id,
            )
        )
        if user is None or not user.is_active or membership is None:
            raise AuthenticationError("Invalid refresh token")
        session.revoked_at = now
        tokens = self._issue_tokens(user.id, session.organization_id, membership.role, now)
        await self._session.commit()
        return tokens

    async def logout(self, token: str) -> None:
        """Revoke a refresh session when it exists."""
        session = await self._session.scalar(
            select(RefreshSession).where(
                RefreshSession.token_hash == hash_refresh_token(token),
                RefreshSession.revoked_at.is_(None),
            )
        )
        if session is not None:
            session.revoked_at = datetime.now(UTC)
            await self._session.commit()

    def _issue_tokens(
        self,
        user_id: UUID,
        organization_id: UUID,
        role: OrganizationRole,
        now: datetime,
    ) -> TokenResponse:
        access_token, expires_in = create_access_token(
            user_id,
            organization_id,
            role,
            self._settings,
        )
        refresh_token, token_hash = create_refresh_token()
        self._session.add(
            RefreshSession(
                user_id=user_id,
                organization_id=organization_id,
                token_hash=token_hash,
                created_at=now,
                expires_at=now + timedelta(days=self._settings.refresh_token_days),
                revoked_at=None,
            )
        )
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
        )
