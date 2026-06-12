"""Rate-limit por usuario + presupuesto mensual de tokens (Redis).

Mantiene el costo predecible y evita exceder el free tier de Groq.
"""

from datetime import UTC, datetime

from core.config import get_settings
from core.errors import BudgetExceededError, RateLimitedError
from core.redis import get_redis

RATE_LIMIT_PER_MINUTE = 20  # llamadas LLM por usuario por minuto


def _month_key(user_id: str) -> str:
    return f"llm:budget:{user_id}:{datetime.now(UTC):%Y%m}"


def _rate_key(user_id: str) -> str:
    return f"llm:rate:{user_id}:{datetime.now(UTC):%Y%m%d%H%M}"


async def check_rate_limit(user_id: str) -> None:
    redis = get_redis()
    key = _rate_key(user_id)
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 120)
    if count > RATE_LIMIT_PER_MINUTE:
        raise RateLimitedError(
            "Pará un toque 😅 — demasiados mensajes seguidos. Probá en un minuto."
        )


async def check_budget(user_id: str) -> None:
    redis = get_redis()
    used = await redis.get(_month_key(user_id))
    if used is not None and int(used) >= get_settings().llm_monthly_budget_tokens:
        raise BudgetExceededError(
            "Llegaste al límite mensual de uso de IA. Se renueva el mes que viene."
        )


async def consume_tokens(user_id: str, tokens: int) -> None:
    redis = get_redis()
    key = _month_key(user_id)
    await redis.incrby(key, tokens)
    # expira a los ~40 días: cubre el mes en curso y se limpia solo
    await redis.expire(key, 60 * 60 * 24 * 40)
