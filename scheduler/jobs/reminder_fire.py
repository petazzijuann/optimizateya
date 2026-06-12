"""Dispara recordatorios vencidos con inline keyboard hecho/snooze/cancelar."""

from aiogram import Bot

from bot.keyboards import reminder_fire_kb
from core.database import session_scope
from core.logging import get_logger, hash_user_id
from core.models import User
from scheduler.manager import due_reminders, mark_fired

log = get_logger(__name__)


async def fire_due(bot: Bot) -> int:
    fired = 0
    async with session_scope() as session:
        for reminder in await due_reminders(session):
            user = await session.get(User, reminder.user_id)
            if user is None or user.deleted_at is not None:
                reminder.status = "cancelled"
                continue
            await mark_fired(session, reminder, user)
            try:
                await bot.send_message(
                    user.telegram_id,
                    f"⏰ *{reminder.title}*",
                    reply_markup=reminder_fire_kb(reminder.id),
                )
                fired += 1
                log.info("reminder_fired", user=hash_user_id(user.id))
            except Exception:
                log.exception("reminder_send_failed", user=hash_user_id(user.id))
    return fired
