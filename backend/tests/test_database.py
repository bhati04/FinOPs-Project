"""Database lifecycle tests for synchronous worker entrypoints."""

import asyncio

import pytest

from cloudwise.core import database


def test_worker_jobs_dispose_the_pool_on_their_own_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sequential Celery jobs must not reuse asyncpg connections from a closed loop."""
    job_loops: list[asyncio.AbstractEventLoop] = []
    dispose_loops: list[asyncio.AbstractEventLoop] = []

    async def job(result: int) -> int:
        job_loops.append(asyncio.get_running_loop())
        return result

    async def fake_dispose_engine() -> None:
        dispose_loops.append(asyncio.get_running_loop())

    monkeypatch.setattr(database, "dispose_engine", fake_dispose_engine)

    assert database.run_async_job(job(1)) == 1
    assert database.run_async_job(job(2)) == 2
    assert dispose_loops == job_loops
    assert job_loops[0] is not job_loops[1]
