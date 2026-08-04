"""FastAPI identity and organization authorization dependencies."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cloudwise.core.config import get_settings
from cloudwise.core.database import get_db_session
from cloudwise.identity.models import User
from cloudwise.identity.security import InvalidAccessTokenError, decode_access_token
from cloudwise.identity.service import AuthenticatedUser, IdentityService
from cloudwise.organizations.models import Organization, OrganizationMembership

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_identity_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> IdentityService:
    """Build a request-scoped identity service."""
    return IdentityService(session, get_settings())


async def get_current_user(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuthenticatedUser:
    """Resolve and verify the access token's persisted tenant membership."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        claims = decode_access_token(token, get_settings())
    except InvalidAccessTokenError as exc:
        raise unauthorized from exc
    result = await session.execute(
        select(User, OrganizationMembership, Organization)
        .join(OrganizationMembership, OrganizationMembership.user_id == User.id)
        .join(Organization, Organization.id == OrganizationMembership.organization_id)
        .where(
            User.id == claims.user_id,
            User.is_active.is_(True),
            OrganizationMembership.organization_id == claims.organization_id,
            OrganizationMembership.role == claims.role,
        )
    )
    row = result.one_or_none()
    if row is None:
        raise unauthorized
    user, membership, organization = row
    authenticated = AuthenticatedUser(
        user_id=user.id,
        email=user.email,
        organization_id=organization.id,
        organization_name=organization.name,
        role=membership.role,
    )
    request.state.audit_actor_user_id = authenticated.user_id
    request.state.audit_organization_id = authenticated.organization_id
    return authenticated


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
