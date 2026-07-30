"""Organization persistence models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cloudwise.core.database import Base


class OrganizationRole(StrEnum):
    """Organization authorization roles."""

    OWNER = "owner"
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class Organization(Base):
    """Tenant boundary for all future customer data."""

    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    memberships: Mapped[list[OrganizationMembership]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )


class OrganizationMembership(Base):
    """A user's role within one organization."""

    __tablename__ = "organization_memberships"
    __table_args__ = (UniqueConstraint("organization_id", "user_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    role: Mapped[OrganizationRole] = mapped_column(
        Enum(OrganizationRole, name="organization_role"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    organization: Mapped[Organization] = relationship(back_populates="memberships")
