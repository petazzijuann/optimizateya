"""Encolado de jobs arq desde el bot/API."""

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from core.config import get_settings

_pool: ArqRedis | None = None


async def get_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    return _pool


def set_pool(pool) -> None:
    """Inyección para tests."""
    global _pool
    _pool = pool


async def enqueue(job_name: str, **kwargs) -> None:
    pool = await get_pool()
    await pool.enqueue_job(job_name, **kwargs)
