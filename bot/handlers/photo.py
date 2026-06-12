"""Imágenes: OCR + análisis semántico en el worker."""

from aiogram import F, Router
from aiogram.types import Message

from worker.queue import enqueue

router = Router(name="photo")


@router.message(F.photo)
async def on_photo(message: Message, user, session) -> None:
    photo = message.photo[-1]  # mayor resolución
    await enqueue(
        "process_image",
        user_id=user.id,
        chat_id=message.chat.id,
        file_id=photo.file_id,
        caption=message.caption or "",
    )
    await message.answer("👀 Mirando la imagen...")
