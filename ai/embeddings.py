"""Embeddings para la memoria semántica (nomic-embed-text vía Ollama, gratis).

Si Ollama no está disponible (ej. en prod sin GPU), devolvemos None y la
memoria cae a búsqueda por texto (ILIKE) — degradación elegante, nunca error.
"""

from openai import AsyncOpenAI

from core.config import get_settings
from core.logging import get_logger
from core.models import EMBEDDING_DIMS

log = get_logger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        s = get_settings()
        _client = AsyncOpenAI(base_url=s.ollama_base_url, api_key="ollama")
    return _client


def set_embeddings_client(client) -> None:
    """Inyección para tests."""
    global _client
    _client = client


async def embed_text(text: str) -> list[float] | None:
    try:
        resp = await _get_client().embeddings.create(
            model=get_settings().embed_model,
            input=text[:8000],
        )
        vec = resp.data[0].embedding
        if len(vec) != EMBEDDING_DIMS:
            log.warning("embedding_dims_mismatch", got=len(vec), expected=EMBEDDING_DIMS)
            return None
        return vec
    except Exception as exc:
        log.warning("embedding_unavailable", error=type(exc).__name__)
        return None
