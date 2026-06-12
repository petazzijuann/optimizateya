"""Ranking global materializado en Redis Sorted Set (O(log n) por update)."""

from core.redis import get_redis

LEADERBOARD_KEY = "leaderboard:global"


async def incr(user_id: str, points: int) -> None:
    await get_redis().zincrby(LEADERBOARD_KEY, points, user_id)


async def set_score(user_id: str, points: int) -> None:
    await get_redis().zadd(LEADERBOARD_KEY, {user_id: points})


async def remove(user_id: str) -> None:
    await get_redis().zrem(LEADERBOARD_KEY, user_id)


async def rank(user_id: str) -> int | None:
    """Posición 1-based; None si el usuario no está en el ranking."""
    r = await get_redis().zrevrank(LEADERBOARD_KEY, user_id)
    return None if r is None else r + 1


async def top(n: int = 10) -> list[tuple[str, int]]:
    rows = await get_redis().zrevrange(LEADERBOARD_KEY, 0, n - 1, withscores=True)
    return [(member, int(score)) for member, score in rows]


async def total_players() -> int:
    return await get_redis().zcard(LEADERBOARD_KEY)


async def all_scores() -> list[tuple[str, int]]:
    """Para el snapshot periódico a Postgres."""
    rows = await get_redis().zrevrange(LEADERBOARD_KEY, 0, -1, withscores=True)
    return [(member, int(score)) for member, score in rows]
