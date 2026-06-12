"""Callbacks de inline buttons: recordatorios (hecho/snooze/cancelar) y borrado total."""

from aiogram import F, Router
from aiogram.types import CallbackQuery

from core.errors import DomainError
from core.models import Reminder
from domain import reminders
from domain.privacy import hard_delete_user
from gamification import leaderboard

router = Router(name="callbacks")


async def _get_reminder(session, user, reminder_id: str) -> Reminder | None:
    reminder = await session.get(Reminder, reminder_id)
    if reminder is None or reminder.user_id != user.id:
        return None
    return reminder


@router.callback_query(F.data.startswith("rem:"))
async def cb_reminder(callback: CallbackQuery, user, session) -> None:
    _, action, reminder_id = callback.data.split(":", 2)
    reminder = await _get_reminder(session, user, reminder_id)
    if reminder is None:
        await callback.answer("Ese recordatorio ya no existe.", show_alert=True)
        return
    try:
        if action == "done":
            reminder = await reminders.complete_reminder(session, user, reminder)
            nice = "a tiempo 💪" if reminder.completed_on_time else "💪"
            await callback.message.edit_text(f"✅ *{reminder.title}* — cumplido {nice}")
        elif action == "snooze":
            reminder = await reminders.snooze_reminder(session, user, reminder, minutes=15)
            await callback.message.edit_text(f"😴 Te lo recuerdo en 15 min: *{reminder.title}*")
        elif action == "cancel":
            await reminders.cancel_reminder(session, user, reminder)
            await callback.message.edit_text(f"🗑 Cancelado: *{reminder.title}*")
    except DomainError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await callback.answer()


@router.callback_query(F.data == "wipe:confirm")
async def cb_wipe_confirm(callback: CallbackQuery, user, session) -> None:
    await leaderboard.remove(user.id)
    await hard_delete_user(session, user)
    await callback.message.edit_text(
        "🧹 Listo. Borré todos tus datos y archivos.\n"
        "Si querés volver a empezar, mandá /start. ¡Gracias por probarme!"
    )
    await callback.answer()


@router.callback_query(F.data == "wipe:cancel")
async def cb_wipe_cancel(callback: CallbackQuery) -> None:
    await callback.message.edit_text("Uff, menos mal 😅 No borré nada. Seguimos como si nada.")
    await callback.answer()
