"""GC de retención: hard-delete de usuarios soft-borrados hace +30 días."""

from core.database import session_scope
from core.logging import get_logger
from domain.privacy import gc_expired_tombstones

log = get_logger(__name__)


async def run_gc() -> int:
    async with session_scope() as session:
        n = await gc_expired_tombstones(session)
    if n:
        log.info("retention_gc_done", purged=n)
    return n
