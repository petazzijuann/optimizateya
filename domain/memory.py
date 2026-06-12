"""Memory Bubbles: guardar notas/archivos, indexar (pgvector) y recuperar.

Búsqueda: similitud coseno sobre embeddings filtrada SIEMPRE por user_id.
Si no hay embeddings disponibles (Ollama caído), degrada a búsqueda por texto.
"""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.embeddings import embed_text
from core import storage
from core.errors import ValidationError
from core.events import DomainEvent, get_event_bus
from core.logging import get_logger
from core.models import MemoryItem, User

log = get_logger(__name__)


async def save_note(
    session: AsyncSession,
    user: User,
    title: str,
    content: str,
    kind: str = "note",
    tags: list[str] | None = None,
    storage_key: str | None = None,
    ocr_text: str | None = None,
) -> MemoryItem:
    if not (title.strip() or content.strip()):
        raise ValidationError("La nota está vacía.")
    embedding = await embed_text(f"{title}\n{content}\n{ocr_text or ''}")
    item = MemoryItem(
        user_id=user.id,
        kind=kind,
        title=title.strip() or content.strip()[:60],
        raw_text=content.strip() or None,
        ocr_text=ocr_text,
        tags=tags or [],
        storage_key=storage_key,
        embedding=embedding,
    )
    session.add(item)
    await session.flush()
    await get_event_bus().publish(
        DomainEvent(type="memory.saved", user_id=user.id, payload={"memory_id": item.id})
    )
    return item


async def save_file(
    session: AsyncSession,
    user: User,
    data: bytes,
    filename: str,
    kind: str,
    title: str,
    text_content: str = "",
    content_type: str = "application/octet-stream",
) -> MemoryItem:
    """Sube el archivo al storage bajo el prefijo del usuario y lo indexa."""
    key = f"{storage.user_prefix(user.id)}{uuid.uuid4().hex}-{filename}"
    try:
        await storage.upload_bytes(key, data, content_type)
    except Exception as exc:
        # sin storage configurado igual guardamos la parte textual
        log.warning("storage_upload_failed", error=type(exc).__name__)
        key = None  # type: ignore[assignment]
    return await save_note(
        session,
        user,
        title=title,
        content=text_content,
        kind=kind,
        storage_key=key,
        ocr_text=text_content or None,
    )


async def search(session: AsyncSession, user: User, query: str, limit: int = 5) -> list[MemoryItem]:
    """Recuperación semántica (cosine) con fallback a texto."""
    query = query.strip()
    if not query:
        return []
    query_vec = await embed_text(query)
    if query_vec is not None:
        rows = await session.execute(
            select(MemoryItem)
            .where(
                MemoryItem.user_id == user.id,
                MemoryItem.deleted_at.is_(None),
                MemoryItem.embedding.is_not(None),
            )
            .order_by(MemoryItem.embedding.cosine_distance(query_vec))
            .limit(limit)
        )
        results = list(rows.scalars())
        if results:
            return results
    # fallback: búsqueda por texto
    pattern = f"%{query}%"
    rows = await session.execute(
        select(MemoryItem)
        .where(
            MemoryItem.user_id == user.id,
            MemoryItem.deleted_at.is_(None),
            or_(
                MemoryItem.title.ilike(pattern),
                MemoryItem.raw_text.ilike(pattern),
                MemoryItem.ocr_text.ilike(pattern),
            ),
        )
        .order_by(MemoryItem.created_at.desc())
        .limit(limit)
    )
    return list(rows.scalars())


def format_memory_line(item: MemoryItem) -> str:
    icon = {"note": "📝", "image": "🖼", "pdf": "📄", "document": "📎", "link": "🔗"}.get(
        item.kind, "🫧"
    )
    snippet = (item.raw_text or item.ocr_text or "")[:80]
    line = f"{icon} *{item.title}*"
    if snippet and snippet.lower() != item.title.lower():
        line += f"\n   {snippet}"
    return line
