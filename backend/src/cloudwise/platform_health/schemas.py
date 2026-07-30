"""Public health API schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class LivenessResponse(BaseModel):
    """Process liveness response."""

    model_config = ConfigDict(extra="forbid")
    status: Literal["ok"]


class DependencyStatus(BaseModel):
    """Non-sensitive dependency state."""

    model_config = ConfigDict(extra="forbid")
    status: Literal["up", "down"]


class ReadinessResponse(BaseModel):
    """Dependency readiness response."""

    model_config = ConfigDict(extra="forbid")
    status: Literal["ready", "not_ready"]
    checks: dict[str, DependencyStatus]
