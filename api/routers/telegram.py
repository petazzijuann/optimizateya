"""Webhook de Telegram: el secret en el path valida el origen."""

import asyncio

from aiogram.types import Update
from fastapi import APIRouter, HTTPException, Request

from core.config import get_settings
from core.logging import get_logger

log = get_logger(__name__)
router = APIRouter()

_background: set[asyncio.Task] = set()


@router.post("/webhook/telegram/{secret}")
async def telegram_webhook(secret: str, request: Request) -> dict:
    if secret != get_settings().telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="forbidden")
    payload = await request.json()
    update = Update.model_validate(payload)
    bot = request.app.state.bot
    dp = request.app.state.dispatcher
    # procesar en background: respondemos 200 ya y Telegram no reintenta
    task = asyncio.create_task(dp.feed_update(bot, update))
    _background.add(task)
    task.add_done_callback(_background.discard)
    return {"ok": True}
