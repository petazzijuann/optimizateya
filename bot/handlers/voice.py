"""Notas de voz: se encolan al worker (STT) y el resultado vuelve por el mismo chat."""

from aiogram import F, Router
from aiogram.types import Message

from worker.queue import enqueue

router = Router(name="voice")

MAX_VOICE_SECONDS = 300


@router.message(F.voice | F.audio)
async def on_voice(message: Message, user, session) -> None:
    media = message.voice or message.audio
    if media.duration and media.duration > MAX_VOICE_SECONDS:
        await message.answer("Uff, muy largo ese audio 😅 Mandame uno de menos de 5 minutos.")
        return
    await enqueue(
        "transcribe_voice",
        user_id=user.id,
        chat_id=message.chat.id,
        file_id=media.file_id,
    )
    await message.answer("🎙 Escuchando tu nota...")
