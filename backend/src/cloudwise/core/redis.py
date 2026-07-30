"""Redis client lifecycle."""

from redis.asyncio import Redis

from cloudwise.core.config import get_settings

_redis: Redis | None = None


def get_redis() -> Redis:
    """Create the Redis client lazily."""
    global _redis
    if _redis is None:
        _redis = Redis.from_url(str(get_settings().redis_url), decode_responses=True)
    return _redis


async def close_redis() -> None:
    """Close the shared Redis client during shutdown."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
