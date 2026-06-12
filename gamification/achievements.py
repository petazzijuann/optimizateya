"""Evaluación de logros: arma stats agregadas y desbloquea lo que corresponda."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import GamificationState, PointEvent, UserAchievement
from core.redis import get_redis
from gamification.catalog import CATALOG, AchievementDef, AchievementStats

EARLY_COUNTER_KEY = "ach:early:{user_id}"  # completados antes de las 8 AM (lo alimenta el engine)


async def build_stats(session: AsyncSession, user_id: str) -> AchievementStats:
    async def _count(*types: str) -> int:
        rows = await session.execute(
            select(func.count())
            .select_from(PointEvent)
            .where(PointEvent.user_id == user_id, PointEvent.event_type.in_(types))
        )
        return rows.scalar_one()

    memories = await _count("memory.saved")
    completed = await _count("reminder.completed_on_time", "reminder.completed_late")
    early_raw = await get_redis().get(EARLY_COUNTER_KEY.format(user_id=user_id))
    state = await session.get(GamificationState, user_id)
    return AchievementStats(
        memories_saved=memories,
        reminders_completed=completed,
        early_completions=int(early_raw or 0),
        current_streak=state.current_streak if state else 0,
    )


async def evaluate(session: AsyncSession, user_id: str) -> list[AchievementDef]:
    """Desbloquea logros nuevos. Devuelve los recién conseguidos (sin otorgar puntos acá)."""
    rows = await session.execute(
        select(UserAchievement.achievement_code).where(UserAchievement.user_id == user_id)
    )
    unlocked = {code for (code,) in rows}
    pending = [a for a in CATALOG if a.code not in unlocked]
    if not pending:
        return []

    stats = await build_stats(session, user_id)
    newly = [a for a in pending if a.condition(stats)]
    for ach in newly:
        session.add(UserAchievement(user_id=user_id, achievement_code=ach.code))
    if newly:
        await session.flush()
    return newly
