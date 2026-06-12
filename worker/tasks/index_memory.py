"""Reindexado de memoria: genera embeddings para ítems que quedaron sin vector."""

from sqlalchemy import select

from ai.embeddings import embed_text
from core.logging import get_logger
from core.models import MemoryItem
from worker.tasks.common import session_scope

log = get_logger(__name__)


async def index_memory(ctx, memory_id: str) -> None:
    async with session_scope() as session:
        item = await session.get(MemoryItem, memory_id)
        if item is None or item.embedding is not None:
            return
        vec = await embed_text(f"{item.title}\n{item.raw_text or ''}\n{item.ocr_text or ''}")
        if vec is not None:
            item.embedding = vec
            log.info("memory_indexed", memory_id=memory_id)


async def reindex_missing(ctx, batch: int = 50) -> int:
    """Pasada periódica: indexa ítems sin embedding (ej: Ollama estaba caído)."""
    indexed = 0
    async with session_scope() as session:
        rows = await session.execute(
            select(MemoryItem)
            .where(MemoryItem.embedding.is_(None), MemoryItem.deleted_at.is_(None))
            .limit(batch)
        )
        for item in rows.scalars():
            vec = await embed_text(f"{item.title}\n{item.raw_text or ''}\n{item.ocr_text or ''}")
            if vec is not None:
                item.embedding = vec
                indexed += 1
    if indexed:
        log.info("memory_reindexed", count=indexed)
    return indexed
