"""Throttling por usuario (Redis): corta floods antes de llegar al NLU."""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from core.redis import get_redis

MAX_UPDATES = 15  # por ventana
WINDOW_SECONDS = 10


class RateLimitMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        message = event.message if isinstance(event, Update) else None
        if message is not None and message.from_user is not None:
            redis = get_redis()
            key = f"throttle:{message.from_user.id}"
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, WINDOW_SECONDS)
            if count > MAX_UPDATES:
                if count == MAX_UPDATES + 1:
                    await message.answer("Despacio 😅 dame unos segundos.")
                return None
        return await handler(event, data)
