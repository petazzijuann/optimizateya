"""Privacidad: exportación completa y borrado (tombstone + hard delete).

`/exportar` arma un JSON con todos los datos del usuario.
`/borrartodo` (confirmado) hace hard delete inmediato en DB + R2.
El GC de retención elimina tombstones vencidos (gracia 30 días).
"""

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core import storage
from core.logging import get_logger, hash_user_id
from core.models import (
    CalendarConnection,
    CalendarEventCache,
    GamificationState,
    List,
    MemoryItem,
    OutboxAction,
    PointEvent,
    Reminder,
    User,
    UserAchievement,
)

log = get_logger(__name__)

RETENTION_GRACE_DAYS = 30


async def export_user_data(session: AsyncSession, user: User) -> bytes:
    """Dump JSON de todos los datos del usuario (sin tokens cifrados)."""

    def _dt(value) -> str | None:
        return value.isoformat() if value else None

    reminders = (
        (await session.execute(select(Reminder).where(Reminder.user_id == user.id)))
        .scalars()
        .all()
    )
    lists = (
        (await session.execute(select(List).where(List.user_id == user.id))).scalars().all()
    )
    memories = (
        (await session.execute(select(MemoryItem).where(MemoryItem.user_id == user.id)))
        .scalars()
        .all()
    )
    points = (
        (await session.execute(select(PointEvent).where(PointEvent.user_id == user.id)))
        .scalars()
        .all()
    )
    state = await session.get(GamificationState, user.id)

    data = {
        "exported_at": datetime.now(UTC).isoformat(),
        "profile": {
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "timezone": user.timezone,
            "locale": user.locale,
            "briefing_hour": user.briefing_hour,
            "created_at": _dt(user.created_at),
        },
        "reminders": [
            {
                "title": r.title,
                "due_at": _dt(r.due_at),
                "status": r.status,
                "recurrence": r.recurrence,
                "completed_at": _dt(r.completed_at),
            }
            for r in reminders
        ],
        "lists": [
            {
                "name": lst.name,
                "items": [
                    {"content": i.content, "is_done": i.is_done, "done_at": _dt(i.done_at)}
                    for i in lst.items
                ],
            }
            for lst in lists
        ],
        "memories": [
            {
                "kind": m.kind,
                "title": m.title,
                "text": m.raw_text,
                "tags": list(m.tags or []),
                "created_at": _dt(m.created_at),
            }
            for m in memories
        ],
        "gamification": {
            "total_points": state.total_points if state else 0,
            "current_streak": state.current_streak if state else 0,
            "longest_streak": state.longest_streak if state else 0,
            "point_events": [
                {"type": p.event_type, "points": p.points, "at": _dt(p.created_at)}
                for p in points
            ],
        },
    }
    return json.dumps(data, ensure_ascii=False, indent=2).encode()


async def hard_delete_user(session: AsyncSession, user: User) -> None:
    """Borrado total e inmediato: DB (cascade) + archivos en R2 + leaderboard."""
    uid = user.id
    try:
        await storage.delete_user_prefix(uid)
    except Exception as exc:
        log.warning("r2_delete_failed", user=hash_user_id(uid), error=type(exc).__name__)

    # el resto cae por ON DELETE CASCADE al borrar el user
    for model in (OutboxAction, CalendarEventCache, CalendarConnection, UserAchievement):
        await session.execute(delete(model).where(model.user_id == uid))
    await session.execute(delete(User).where(User.id == uid))
    await session.flush()
    log.info("user_hard_deleted", user=hash_user_id(uid))


async def gc_expired_tombstones(session: AsyncSession) -> int:
    """Hard-delete de usuarios soft-borrados hace más de RETENTION_GRACE_DAYS."""
    cutoff = datetime.now(UTC) - timedelta(days=RETENTION_GRACE_DAYS)
    rows = await session.execute(
        select(User).where(User.deleted_at.is_not(None), User.deleted_at < cutoff)
    )
    users = list(rows.scalars())
    for user in users:
        await hard_delete_user(session, user)
    return len(users)


PRIVACY_POLICY_TEXT = (
    "🔒 *Privacidad en Optimizate Ya*\n\n"
    "• Guardamos solo lo imprescindible: tu perfil de Telegram, recordatorios, "
    "listas y lo que vos elegís recordar.\n"
    "• Tus archivos se cifran en tránsito y en reposo.\n"
    "• Los tokens de calendario se guardan cifrados; nunca en claro.\n"
    "• No leemos ni logueamos el contenido de tus mensajes.\n"
    "• /exportar te da todos tus datos. /borrartodo los elimina por completo.\n"
)
