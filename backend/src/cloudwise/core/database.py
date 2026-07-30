"""Async PostgreSQL engine lifecycle."""

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from cloudwise.core.config import get_settings

_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    """Create the connection pool lazily."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            get_settings().database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
        )
    return _engine


async def dispose_engine() -> None:
    """Dispose the process pool during application shutdown."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
