"""Comandos visibles del bot + utilidades CLI (set-webhook)."""

import asyncio
import sys

from aiogram import Bot
from aiogram.types import BotCommand

from core.config import get_settings

BOT_COMMANDS = [
    BotCommand(command="start", description="Empezar / configurar"),
    BotCommand(command="puntos", description="Tus puntos"),
    BotCommand(command="racha", description="Tu racha de días"),
    BotCommand(command="ranking", description="Ranking global"),
    BotCommand(command="stats", description="Tus estadísticas"),
    BotCommand(command="logros", description="Logros desbloqueados"),
    BotCommand(command="historial", description="Última actividad"),
    BotCommand(command="calendario", description="Conectar Google/Outlook"),
    BotCommand(command="exportar", description="Exportar tus datos"),
    BotCommand(command="borrartodo", description="Borrar todos tus datos"),
    BotCommand(command="privacidad", description="Política de privacidad"),
    BotCommand(command="ayuda", description="Cómo usarme"),
]


async def setup_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(BOT_COMMANDS)


async def set_webhook() -> None:
    s = get_settings()
    bot = Bot(token=s.telegram_bot_token)
    try:
        await setup_bot_commands(bot)
        await bot.set_webhook(
            url=s.webhook_url,
            drop_pending_updates=False,
            allowed_updates=["message", "callback_query", "edited_message"],
        )
        info = await bot.get_webhook_info()
        print(f"Webhook registrado: {info.url}")
    finally:
        await bot.session.close()


async def delete_webhook() -> None:
    s = get_settings()
    bot = Bot(token=s.telegram_bot_token)
    try:
        await bot.delete_webhook()
        print("Webhook eliminado.")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "set-webhook"
    if cmd == "set-webhook":
        asyncio.run(set_webhook())
    elif cmd == "delete-webhook":
        asyncio.run(delete_webhook())
    else:
        print("Uso: python -m bot.commands [set-webhook|delete-webhook]")
