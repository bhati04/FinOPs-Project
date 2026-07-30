"""Version-one API router composition."""

from fastapi import APIRouter

from cloudwise.aws_accounts.router import router as aws_accounts_router
from cloudwise.identity.router import router as identity_router
from cloudwise.platform_health.router import router as health_router

api_router = APIRouter()

api_router.include_router(
    health_router,
    prefix="/health",
    tags=["platform-health"],
)

api_router.include_router(
    identity_router,
    prefix="/auth",
    tags=["identity"],
)

api_router.include_router(
    aws_accounts_router,
    prefix="/aws-accounts",
    tags=["aws-accounts"],
)
