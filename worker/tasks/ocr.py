"""Imagen → OCR (Tesseract) + análisis semántico → memoria o NLU."""

from ai.vision import analyze_image, extract_text
from bot.processing import handle_text
from core.logging import get_logger, hash_user_id
from domain import memory
from worker.tasks.common import download_telegram_file, get_user, session_scope

log = get_logger(__name__)


async def process_image(ctx, user_id: str, chat_id: int, file_id: str, caption: str = "") -> None:
    bot = ctx["bot"]
    try:
        image = await download_telegram_file(bot, file_id)
    except Exception:
        log.exception("image_download_failed", user=hash_user_id(user_id))
        await bot.send_message(chat_id, "No pude bajar la imagen 😞 Probá de nuevo.")
        return

    ocr_text = await extract_text(image)
    analysis = await analyze_image(image)

    async with session_scope() as session:
        user = await get_user(session, user_id)
        if user is None:
            return

        if caption.strip():
            # el caption es la instrucción: la imagen aporta su texto extraído
            prompt = caption.strip()
            if ocr_text:
                prompt += f"\n\n(Texto extraído de la imagen: {ocr_text[:1500]})"
            reply = await handle_text(session, user, prompt)
            await bot.send_message(chat_id, reply)
            return

        item = await memory.save_file(
            session,
            user,
            data=image,
            filename="imagen.jpg",
            kind="image",
            title=analysis.title,
            text_content=ocr_text,
            content_type="image/jpeg",
        )
        msg = f"🫧 Guardé la imagen en tu memoria como *{item.title}*."
        if analysis.summary:
            msg += f"\n_{analysis.summary}_"
        if analysis.suggested_action == "create_reminder":
            msg += "\n\n💡 Parece algo con fecha. Si querés, decime: _\"recordame esto el ...\"_"
        await bot.send_message(chat_id, msg)


async def process_document(
    ctx,
    user_id: str,
    chat_id: int,
    file_id: str,
    filename: str = "archivo",
    mime_type: str = "",
    caption: str = "",
) -> None:
    """PDF/documento → extracción de texto → memoria indexada."""
    bot = ctx["bot"]
    try:
        data = await download_telegram_file(bot, file_id)
    except Exception:
        log.exception("document_download_failed", user=hash_user_id(user_id))
        await bot.send_message(chat_id, "No pude bajar el archivo 😞 Probá de nuevo.")
        return

    text_content = ""
    if mime_type == "application/pdf" or filename.lower().endswith(".pdf"):
        text_content = _extract_pdf_text(data)
        kind = "pdf"
    else:
        kind = "document"

    async with session_scope() as session:
        user = await get_user(session, user_id)
        if user is None:
            return
        item = await memory.save_file(
            session,
            user,
            data=data,
            filename=filename,
            kind=kind,
            title=caption.strip() or filename,
            text_content=text_content,
            content_type=mime_type or "application/octet-stream",
        )
    await bot.send_message(
        chat_id,
        f"🫧 Guardado en tu memoria: *{item.title}*. Pedímelo cuando quieras "
        f'(_"¿dónde guardé {item.title[:30]}?"_).',
    )


def _extract_pdf_text(data: bytes, max_pages: int = 20) -> str:
    try:
        import io

        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        pages = reader.pages[:max_pages]
        return "\n".join((p.extract_text() or "") for p in pages).strip()[:20000]
    except Exception:
        log.warning("pdf_extract_failed")
        return ""
