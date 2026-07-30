"""Platform health HTTP routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from cloudwise.platform_health.schemas import LivenessResponse, ReadinessResponse
from cloudwise.platform_health.service import HealthService, get_health_service

router = APIRouter()


@router.get(
    "/live",
    response_model=LivenessResponse,
    summary="Check API process liveness",
)
async def liveness() -> LivenessResponse:
    """Return success when the ASGI process can serve requests."""
    return LivenessResponse(status="ok")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Check API dependency readiness",
    responses={503: {"description": "A required dependency is unavailable"}},
)
async def readiness(
    response: Response,
    service: Annotated[HealthService, Depends(get_health_service)],
) -> ReadinessResponse:
    """Report PostgreSQL and Redis availability without exposing connection details."""
    result = await service.readiness()
    if result.status == "not_ready":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result
