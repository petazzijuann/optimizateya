"""Reconciliación periódica de calendarios: encola un sync por usuario conectado."""

from sqlalchemy import select

from core.database import session_scope
from core.logging import get_logger
from core.models import CalendarConnection
from worker.queue import enqueue

log = get_logger(__name__)


async def reconcile_all() -> int:
    async with session_scope() as session:
        rows = await session.execute(select(CalendarConnection.user_id).distinct())
        user_ids = [uid for (uid,) in rows]
    for uid in user_ids:
        await enqueue("calendar_sync", user_id=uid)
    if user_ids:
        log.info("calendar_reconcile_enqueued", users=len(user_ids))
    return len(user_ids)
