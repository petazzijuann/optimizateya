"""Mensajes de texto libres → NLU → dominio."""

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.types import Message

from bot.processing import handle_text

router = Router(name="text")


@router.message(F.text & ~F.text.startswith("/"))
async def on_text(message: Message, user, session) -> None:
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    reply = await handle_text(session, user, message.text or "")
    await message.answer(reply)
