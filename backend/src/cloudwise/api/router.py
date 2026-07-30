"""Version-one API router composition."""

from fastapi import APIRouter

from cloudwise.platform_health.router import router as health_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["platform-health"])
