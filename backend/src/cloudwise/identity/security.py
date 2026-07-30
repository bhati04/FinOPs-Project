"""Password and token security primitives."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import UUID, uuid4

import jwt
from pwdlib import PasswordHash

from cloudwise.core.config import Settings
from cloudwise.organizations.models import OrganizationRole

_password_hash = PasswordHash.recommended()


class InvalidAccessTokenError(ValueError):
    """Raised when an access token cannot be trusted."""


@dataclass(frozen=True)
class AccessTokenClaims:
    """Validated authorization claims."""

    user_id: UUID
    organization_id: UUID
    role: OrganizationRole


def hash_password(password: str) -> str:
    """Hash a password using the configured Argon2id profile."""
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password without exposing hash details."""
    return _password_hash.verify(password, password_hash)


def create_access_token(
    user_id: UUID,
    organization_id: UUID,
    role: OrganizationRole,
    settings: Settings,
) -> tuple[str, int]:
    """Issue a short-lived signed access token."""
    now = datetime.now(UTC)
    expires_in = settings.access_token_minutes * 60
    payload = {
        "sub": str(user_id),
        "org": str(organization_id),
        "role": role.value,
        "type": "access",
        "iss": "cloudwise",
        "aud": "cloudwise-web",
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
        "jti": str(uuid4()),
    }
    token = jwt.encode(
        payload,
        settings.auth_secret_key.get_secret_value(),
        algorithm="HS256",
    )
    return token, expires_in


def decode_access_token(token: str, settings: Settings) -> AccessTokenClaims:
    """Validate signature, expiry, audience, issuer, and tenant claims."""
    try:
        payload = jwt.decode(
            token,
            settings.auth_secret_key.get_secret_value(),
            algorithms=["HS256"],
            audience="cloudwise-web",
            issuer="cloudwise",
        )
        if payload.get("type") != "access":
            raise InvalidAccessTokenError
        return AccessTokenClaims(
            user_id=UUID(str(payload["sub"])),
            organization_id=UUID(str(payload["org"])),
            role=OrganizationRole(str(payload["role"])),
        )
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise InvalidAccessTokenError from exc


def create_refresh_token() -> tuple[str, str]:
    """Create a high-entropy refresh token and its storage-safe hash."""
    token = token_urlsafe(48)
    return token, hash_refresh_token(token)


def hash_refresh_token(token: str) -> str:
    """Hash a refresh token before persistence."""
    return sha256(token.encode("utf-8")).hexdigest()
