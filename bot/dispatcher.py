"""Construcción del Dispatcher de aiogram: routers + middlewares + FSM en Redis."""

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage

from bot.handlers import callbacks, document, gamification, photo, privacy, start, text, voice
from bot.middleware.i18n import I18nMiddleware
from bot.middleware.rate_limit import RateLimitMiddleware
from bot.middleware.user import UserSessionMiddleware
from core.config import get_settings


def create_bot() -> Bot:
    return Bot(
        token=get_settings().telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )


def create_dispatcher(use_redis_fsm: bool = True) -> Dispatcher:
    storage = (
        RedisStorage.from_url(get_settings().redis_url) if use_redis_fsm else MemoryStorage()
    )
    dp = Dispatcher(storage=storage)

    # orden importa: throttle → user/session → i18n
    dp.update.outer_middleware(RateLimitMiddleware())
    dp.update.outer_middleware(UserSessionMiddleware())
    dp.update.outer_middleware(I18nMiddleware())

    dp.include_router(start.router)
    dp.include_router(gamification.router)
    dp.include_router(privacy.router)
    dp.include_router(callbacks.router)
    dp.include_router(voice.router)
    dp.include_router(photo.router)
    dp.include_router(document.router)
    dp.include_router(text.router)  # catch-all de texto: SIEMPRE último
    return dp
