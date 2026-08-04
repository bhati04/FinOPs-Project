"""Version-one API router composition."""

from fastapi import APIRouter

from cloudwise.aws_accounts.router import router as aws_accounts_router
from cloudwise.cost_management.router import router as cost_router
from cloudwise.identity.router import router as identity_router
from cloudwise.metrics.router import router as metric_router
from cloudwise.platform_health.router import router as health_router
from cloudwise.recommendations.router import router as recommendation_router
from cloudwise.reports.router import router as report_router
from cloudwise.scans.router import router as scans_router

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

api_router.include_router(
    scans_router,
    tags=["inventory-scans"],
)

api_router.include_router(
    cost_router,
    prefix="/costs",
    tags=["cost-management"],
)

api_router.include_router(
    metric_router,
    prefix="/metrics",
    tags=["resource-metrics"],
)

api_router.include_router(
    recommendation_router,
    prefix="/recommendations",
    tags=["recommendations"],
)

api_router.include_router(
    report_router,
    prefix="/reports",
    tags=["reports-and-audit"],
)
