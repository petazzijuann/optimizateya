"""Briefing diario a la hora local de cada usuario (idempotente vía Redis)."""

from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot
from sqlalchemy import select

from core.database import session_scope
from core.logging import get_logger, hash_user_id
from core.models import User
from core.redis import get_redis
from domain.briefing import build_briefing

log = get_logger(__name__)


async def send_briefings(bot: Bot) -> int:
    """Corre cada ~10 min; envía a quienes 'les llegó la hora' y aún no recibieron hoy."""
    sent = 0
    redis = get_redis()
    async with session_scope() as session:
        rows = await session.execute(
            select(User).where(User.briefing_hour.is_not(None), User.deleted_at.is_(None))
        )
        for user in rows.scalars():
            now_local = datetime.now(ZoneInfo(user.timezone))
            if now_local.hour != user.briefing_hour:
                continue
            key = f"briefing:{user.id}:{now_local:%Y%m%d}"
            if await redis.set(key, "1", nx=True, ex=60 * 60 * 36) is None:
                continue  # ya enviado hoy
            try:
                text = await build_briefing(session, user)
                await bot.send_message(user.telegram_id, text)
                sent += 1
            except Exception:
                log.exception("briefing_send_failed", user=hash_user_id(user.id))
    return sent
