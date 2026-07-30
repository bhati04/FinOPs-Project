"""Identity security primitive tests."""

from uuid import uuid4

import pytest

from cloudwise.core.config import Settings
from cloudwise.identity.security import (
    InvalidAccessTokenError,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from cloudwise.organizations.models import OrganizationRole


def test_passwords_are_hashed_with_argon2_and_verified() -> None:
    password = "correct horse battery staple"
    password_digest = hash_password(password)

    assert password_digest.startswith("$argon2")
    assert verify_password(password, password_digest)
    assert not verify_password("incorrect password", password_digest)


def test_access_token_preserves_tenant_context() -> None:
    settings = Settings(environment="test")
    user_id = uuid4()
    organization_id = uuid4()

    token, expires_in = create_access_token(
        user_id,
        organization_id,
        OrganizationRole.OWNER,
        settings,
    )
    claims = decode_access_token(token, settings)

    assert expires_in == 900
    assert claims.user_id == user_id
    assert claims.organization_id == organization_id
    assert claims.role is OrganizationRole.OWNER


def test_tampered_access_token_is_rejected() -> None:
    settings = Settings(environment="test")
    token, _ = create_access_token(
        uuid4(),
        uuid4(),
        OrganizationRole.VIEWER,
        settings,
    )

    with pytest.raises(InvalidAccessTokenError):
        decode_access_token(token + "tampered", settings)


def test_refresh_tokens_are_stored_only_as_hashes() -> None:
    token, token_hash = create_refresh_token()

    assert token != token_hash
    assert len(token_hash) == 64
    assert hash_refresh_token(token) == token_hash
