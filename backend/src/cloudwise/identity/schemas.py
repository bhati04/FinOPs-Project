"""Public identity API schemas."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from cloudwise.organizations.models import OrganizationRole


class RegisterRequest(BaseModel):
    """Create the first user and organization membership."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=128)
    organization_name: str = Field(min_length=2, max_length=120)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("email must be valid")
        return normalized


class LoginRequest(BaseModel):
    """Authenticate a user."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    """Rotate a refresh token."""

    model_config = ConfigDict(extra="forbid")
    refresh_token: str = Field(min_length=32, max_length=512)


class LogoutRequest(RefreshRequest):
    """Revoke a refresh token."""


class TokenResponse(BaseModel):
    """Access and refresh credentials."""

    model_config = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class CurrentUserResponse(BaseModel):
    """Safe identity and tenant context."""

    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    email: str
    organization_id: UUID
    organization_name: str
    role: OrganizationRole
