"""Speech-to-text con Groq Whisper (free tier). Detección de idioma automática."""

import io

from groq import AsyncGroq

from core.config import get_settings
from core.logging import get_logger

log = get_logger(__name__)

_groq: AsyncGroq | None = None


def _get_groq() -> AsyncGroq:
    global _groq
    if _groq is None:
        _groq = AsyncGroq(api_key=get_settings().groq_api_key)
    return _groq


def set_groq_client(client) -> None:
    """Inyección para tests."""
    global _groq
    _groq = client


async def transcribe_audio(audio: bytes, filename: str = "voice.ogg") -> str:
    """Transcribe una nota de voz. Nunca loguea el contenido transcripto."""
    buf = io.BytesIO(audio)
    buf.name = filename
    result = await _get_groq().audio.transcriptions.create(
        file=buf,
        model=get_settings().stt_model,
        response_format="text",
    )
    text = result if isinstance(result, str) else getattr(result, "text", "")
    log.info("stt_done", audio_bytes=len(audio), text_chars=len(text))
    return text.strip()
