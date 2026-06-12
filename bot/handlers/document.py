"""Documentos/PDFs: extracción de texto + guardado en memoria, vía worker."""

from aiogram import F, Router
from aiogram.types import Message

from worker.queue import enqueue

router = Router(name="document")

MAX_FILE_MB = 20


@router.message(F.document)
async def on_document(message: Message, user, session) -> None:
    doc = message.document
    if doc.file_size and doc.file_size > MAX_FILE_MB * 1024 * 1024:
        await message.answer(f"Ese archivo pesa mucho 😅 Máximo {MAX_FILE_MB} MB.")
        return
    await enqueue(
        "process_document",
        user_id=user.id,
        chat_id=message.chat.id,
        file_id=doc.file_id,
        filename=doc.file_name or "archivo",
        mime_type=doc.mime_type or "",
        caption=message.caption or "",
    )
    await message.answer("📎 Guardando el archivo en tu memoria...")
