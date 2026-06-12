"""Cliente Redis compartido: cache, leaderboard (ZSET), rate-limit y presupuesto LLM."""

from redis.asyncio import Redis, from_url

from core.config import get_settings

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = from_url(get_settings().redis_url, decode_responses=True)
    return _redis


def set_redis(client: Redis) -> None:
    """Permite inyectar un cliente fake en tests."""
    global _redis
    _redis = client


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
