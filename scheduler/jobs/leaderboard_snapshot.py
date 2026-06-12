"""Reconciliación DB ↔ Redis del ranking (durabilidad ante pérdida de Redis)."""

from sqlalchemy import select

from core.database import session_scope
from core.logging import get_logger
from core.models import GamificationState, User
from gamification import leaderboard

log = get_logger(__name__)


async def snapshot() -> int:
    """La DB (gamification_state) es canónica: re-sincroniza el ZSET."""
    synced = 0
    async with session_scope() as session:
        rows = await session.execute(
            select(GamificationState, User.leaderboard_opt_out, User.deleted_at)
            .join(User, User.id == GamificationState.user_id)
        )
        for state, opt_out, deleted_at in rows.all():
            if opt_out or deleted_at is not None:
                await leaderboard.remove(state.user_id)
            else:
                await leaderboard.set_score(state.user_id, state.total_points)
                synced += 1
    log.info("leaderboard_snapshot", players=synced)
    return synced
