"""Dependency health probes."""

import asyncio
from collections.abc import Awaitable, Callable

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from cloudwise.core.database import get_engine
from cloudwise.core.redis import get_redis
from cloudwise.platform_health.schemas import DependencyStatus, ReadinessResponse

Check = Callable[[], Awaitable[bool]]


class HealthService:
    """Evaluate platform dependencies with bounded latency."""

    def __init__(self, database_check: Check, redis_check: Check, timeout_seconds: float = 2.0):
        self.database_check = database_check
        self.redis_check = redis_check
        self.timeout_seconds = timeout_seconds

    async def readiness(self) -> ReadinessResponse:
        """Check dependencies independently so failures are observable."""
        results = await asyncio.gather(
            self._bounded_check(self.database_check),
            self._bounded_check(self.redis_check),
        )
        checks = {
            "database": DependencyStatus(status="up" if results[0] else "down"),
            "redis": DependencyStatus(status="up" if results[1] else "down"),
        }
        is_ready = all(result for result in results)
        return ReadinessResponse(status="ready" if is_ready else "not_ready", checks=checks)

    async def _bounded_check(self, check: Check) -> bool:
        try:
            return await asyncio.wait_for(check(), timeout=self.timeout_seconds)
        except (TimeoutError, ConnectionError, OSError):
            return False
        except Exception:
            return False


async def check_database(engine: AsyncEngine | None = None) -> bool:
    """Run a minimal database round trip."""
    active_engine = engine or get_engine()
    async with active_engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return True


async def check_redis(client: Redis | None = None) -> bool:
    """Run a minimal Redis round trip."""
    active_client = client or get_redis()
    return bool(await active_client.ping())


def get_health_service() -> HealthService:
    """Construct the default service for FastAPI dependency injection."""
    return HealthService(check_database, check_redis)
