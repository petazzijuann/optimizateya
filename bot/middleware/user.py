"""Middleware: abre sesión de DB, resuelve telegram_id → User y los inyecta al handler.

El handler recibe `session` (AsyncSession, con commit automático al final) y
`user` (modelo de dominio). El aislamiento multi-tenant arranca acá.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from core.database import session_scope
from core.logging import get_logger, hash_user_id, new_request_id
from core.models import User

log = get_logger(__name__)


def _extract_tg_user(event: TelegramObject):
    if isinstance(event, Update):
        for attr in ("message", "callback_query", "edited_message"):
            obj = getattr(event, attr, None)
            if obj is not None and obj.from_user is not None:
                return obj.from_user
    return getattr(event, "from_user", None)


class UserSessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        new_request_id()
        tg_user = _extract_tg_user(event)
        if tg_user is None or tg_user.is_bot:
            return await handler(event, data)

        async with session_scope() as session:
            user = await self._get_or_create(session, tg_user)
            data["session"] = session
            data["user"] = user
            return await handler(event, data)

    @staticmethod
    async def _get_or_create(session, tg_user) -> User:
        from sqlalchemy import select
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = (
            pg_insert(User)
            .values(
                telegram_id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name or "",
                locale="es-AR",
            )
            .on_conflict_do_nothing(index_elements=["telegram_id"])
        )
        await session.execute(stmt)

        rows = await session.execute(select(User).where(User.telegram_id == tg_user.id))
        user = rows.scalar_one()
        if user.deleted_at is not None:
            user.deleted_at = None
        log.info("user_resolved", user=hash_user_id(user.id))
        return user
