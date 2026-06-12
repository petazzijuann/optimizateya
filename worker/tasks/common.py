"""Helpers compartidos por los tasks del worker."""

import io

from aiogram import Bot

from core.database import session_scope
from core.models import User


async def download_telegram_file(bot: Bot, file_id: str) -> bytes:
    file = await bot.get_file(file_id)
    if file.file_path is None:
        raise ValueError("Telegram no devolvió file_path")
    buf = io.BytesIO()
    await bot.download_file(file.file_path, destination=buf)
    return buf.getvalue()


async def get_user(session, user_id: str) -> User | None:
    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        return None
    return user


__all__ = ["download_telegram_file", "get_user", "session_scope"]
