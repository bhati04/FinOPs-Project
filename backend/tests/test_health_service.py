"""Platform health service unit tests."""

import asyncio

from cloudwise.platform_health.service import HealthService


async def test_readiness_bounds_slow_dependency() -> None:
    async def slow() -> bool:
        await asyncio.sleep(0.05)
        return True

    async def succeeds() -> bool:
        return True

    result = await HealthService(slow, succeeds, timeout_seconds=0.001).readiness()

    assert result.status == "not_ready"
    assert result.checks["database"].status == "down"
    assert result.checks["redis"].status == "up"
