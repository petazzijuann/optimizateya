"""Sync de calendario por usuario (pull de eventos al cache local)."""

from core.errors import DomainError
from core.logging import get_logger, hash_user_id
from worker.tasks.common import get_user, session_scope

log = get_logger(__name__)


async def calendar_sync(ctx, user_id: str) -> None:
    from domain.calendar import sync_events

    async with session_scope() as session:
        user = await get_user(session, user_id)
        if user is None:
            return
        try:
            n = await sync_events(session, user)
            log.info("calendar_synced", user=hash_user_id(user_id), events=n)
        except DomainError as exc:
            log.warning("calendar_sync_failed", user=hash_user_id(user_id), reason=exc.code)
