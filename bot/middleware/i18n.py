"""Detección liviana de idioma/región desde Telegram (es-AR por defecto)."""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

_KNOWN = {"es", "en", "pt"}


class I18nMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("user")
        if user is not None and isinstance(event, Update):
            msg = event.message or (event.callback_query and event.callback_query.message)
            tg_user = event.message.from_user if event.message else None
            if tg_user is None and event.callback_query:
                tg_user = event.callback_query.from_user
            lang = (tg_user.language_code or "es") if tg_user else "es"
            base = lang.split("-")[0].lower()
            if base in _KNOWN and not user.locale:
                user.locale = lang
            data["lang"] = base
            _ = msg
        return await handler(event, data)
