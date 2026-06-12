"""Nota de voz → STT (Groq Whisper) → NLU → respuesta en el chat."""

from ai.transcribe import transcribe_audio
from bot.processing import handle_text
from core.logging import get_logger, hash_user_id
from worker.tasks.common import download_telegram_file, get_user, session_scope

log = get_logger(__name__)


async def transcribe_voice(ctx, user_id: str, chat_id: int, file_id: str) -> None:
    bot = ctx["bot"]
    try:
        audio = await download_telegram_file(bot, file_id)
        text = await transcribe_audio(audio)
    except Exception:
        log.exception("transcribe_failed", user=hash_user_id(user_id))
        await bot.send_message(chat_id, "No pude escuchar ese audio 😞 ¿Me lo escribís?")
        return

    if not text:
        await bot.send_message(chat_id, "El audio salió vacío 🤔 Probá de nuevo.")
        return

    async with session_scope() as session:
        user = await get_user(session, user_id)
        if user is None:
            return
        reply = await handle_text(session, user, text)

    await bot.send_message(chat_id, f"🎙 _Escuché:_ «{text}»\n\n{reply}")
