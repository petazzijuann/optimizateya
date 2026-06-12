"""Visión: OCR local con Tesseract + análisis semántico con modelo de visión open.

Pipeline: imagen → OCR (texto crudo, gratis, local) → modelo de visión
(clasifica: ticket/nota/tarea y propone acción). Todo se normaliza a texto
antes del NLU. Nunca se loguea el contenido extraído.
"""

import asyncio
import base64
import io
import json

from openai import AsyncOpenAI
from pydantic import BaseModel

from ai.prompts import VISION_ANALYSIS_PROMPT
from core.config import get_settings
from core.logging import get_logger

log = get_logger(__name__)

_vision_client: AsyncOpenAI | None = None


def _get_vision_client() -> AsyncOpenAI:
    global _vision_client
    if _vision_client is None:
        s = get_settings()
        _vision_client = AsyncOpenAI(base_url=s.llm_base_url, api_key=s.llm_api_key or "missing")
    return _vision_client


def set_vision_client(client) -> None:
    """Inyección para tests."""
    global _vision_client
    _vision_client = client


class ImageAnalysis(BaseModel):
    kind: str = "otro"
    title: str = "Imagen guardada"
    summary: str = ""
    suggested_action: str = "save_memory"


def _ocr_sync(image_bytes: bytes) -> str:
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))
        return pytesseract.image_to_string(img, lang="spa+eng").strip()
    except Exception as exc:
        log.warning("ocr_unavailable", error=type(exc).__name__)
        return ""


async def extract_text(image_bytes: bytes) -> str:
    """OCR local (Tesseract) sin bloquear el event loop."""
    return await asyncio.to_thread(_ocr_sync, image_bytes)


async def analyze_image(image_bytes: bytes) -> ImageAnalysis:
    """Clasificación semántica de la imagen con el modelo de visión."""
    b64 = base64.b64encode(image_bytes).decode()
    try:
        resp = await _get_vision_client().chat.completions.create(
            model=get_settings().vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VISION_ANALYSIS_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                        },
                    ],
                }
            ],
            max_tokens=300,
            temperature=0.1,
        )
        raw = resp.choices[0].message.content or "{}"
        start, end = raw.find("{"), raw.rfind("}")
        data = json.loads(raw[start : end + 1]) if start >= 0 else {}
        return ImageAnalysis(**{k: v for k, v in data.items() if k in ImageAnalysis.model_fields})
    except Exception as exc:
        log.warning("vision_analysis_failed", error=type(exc).__name__)
        return ImageAnalysis()
