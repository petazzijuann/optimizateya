"""Servicio de recordatorios: CRUD, recurrencia, snooze, disparo.

El scheduler (proceso aparte) consulta la DB cada ~30 s y dispara los vencidos:
la DB es la fuente de verdad, no hace falta coordinar jobstores entre procesos.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import NotFoundError, ValidationError
from core.events import DomainEvent, get_event_bus
from core.models import Reminder, User
from domain.dates import parse_natural_datetime

ON_TIME_GRACE = timedelta(minutes=30)

RECURRENCES = {"none", "daily", "weekly", "monthly"}


async def create_reminder(
    session: AsyncSession,
    user: User,
    title: str,
    due_at_natural: str,
    recurrence: str = "none",
) -> Reminder:
    if not title.strip():
        raise ValidationError("El recordatorio necesita un título.")
    if recurrence not in RECURRENCES:
        recurrence = "none"
    due_local = parse_natural_datetime(due_at_natural, user.timezone)
    reminder = Reminder(
        user_id=user.id,
        title=title.strip(),
        due_at=due_local.astimezone(UTC),
        recurrence={"type": recurrence} if recurrence != "none" else None,
    )
    session.add(reminder)
    await session.flush()
    await get_event_bus().publish(
        DomainEvent(type="reminder.created", user_id=user.id, payload={"reminder_id": reminder.id})
    )
    return reminder


async def list_pending(session: AsyncSession, user: User, limit: int = 20) -> list[Reminder]:
    rows = await session.execute(
        select(Reminder)
        .where(Reminder.user_id == user.id, Reminder.status == "pending")
        .order_by(Reminder.due_at)
        .limit(limit)
    )
    return list(rows.scalars())


async def find_by_text(session: AsyncSession, user: User, query: str) -> Reminder:
    rows = await session.execute(
        select(Reminder)
        .where(
            Reminder.user_id == user.id,
            Reminder.status == "pending",
            Reminder.title.ilike(f"%{query.strip()}%"),
        )
        .order_by(Reminder.due_at)
        .limit(1)
    )
    reminder = rows.scalar_one_or_none()
    if reminder is None:
        raise NotFoundError(f"No encontré un recordatorio pendiente que diga '{query}'.")
    return reminder


async def complete_reminder(
    session: AsyncSession, user: User, reminder: Reminder, when: datetime | None = None
) -> Reminder:
    if reminder.user_id != user.id:
        raise NotFoundError("Recordatorio inexistente.")
    when = when or datetime.now(UTC)
    due = reminder.due_at if reminder.due_at.tzinfo else reminder.due_at.replace(tzinfo=UTC)
    on_time = when <= due + ON_TIME_GRACE
    reminder.status = "done"
    reminder.completed_at = when
    reminder.completed_on_time = on_time
    await session.flush()
    event_type = "reminder.completed_on_time" if on_time else "reminder.completed_late"
    await get_event_bus().publish(
        DomainEvent(
            type=event_type,
            user_id=user.id,
            payload={"reminder_id": reminder.id, "completed_at": when.isoformat()},
        )
    )
    return reminder


async def cancel_reminder(session: AsyncSession, user: User, reminder: Reminder) -> None:
    if reminder.user_id != user.id:
        raise NotFoundError("Recordatorio inexistente.")
    reminder.status = "cancelled"
    await session.flush()
    await get_event_bus().publish(
        DomainEvent(
            type="reminder.cancelled", user_id=user.id, payload={"reminder_id": reminder.id}
        )
    )


async def snooze_reminder(
    session: AsyncSession, user: User, reminder: Reminder, minutes: int = 15
) -> Reminder:
    if reminder.user_id != user.id:
        raise NotFoundError("Recordatorio inexistente.")
    base = max(datetime.now(UTC), reminder.due_at.replace(tzinfo=reminder.due_at.tzinfo or UTC))
    reminder.due_at = base + timedelta(minutes=minutes)
    reminder.fired_at = None
    await session.flush()
    return reminder


def next_occurrence(reminder: Reminder, timezone: str) -> datetime | None:
    """Próximo due_at (UTC) para recurrentes; None si no recurre."""
    if not reminder.recurrence:
        return None
    rtype = reminder.recurrence.get("type", "none")
    due = reminder.due_at if reminder.due_at.tzinfo else reminder.due_at.replace(tzinfo=UTC)
    local = due.astimezone(ZoneInfo(timezone))
    if rtype == "daily":
        nxt = local + timedelta(days=1)
    elif rtype == "weekly":
        nxt = local + timedelta(weeks=1)
    elif rtype == "monthly":
        nxt = local + relativedelta(months=1)
    else:
        return None
    return nxt.astimezone(UTC)


def format_reminder_line(reminder: Reminder, timezone: str) -> str:
    due = reminder.due_at if reminder.due_at.tzinfo else reminder.due_at.replace(tzinfo=UTC)
    local = due.astimezone(ZoneInfo(timezone))
    rec = ""
    if reminder.recurrence:
        rec = {" daily": " 🔁 diario", " weekly": " 🔁 semanal", " monthly": " 🔁 mensual"}.get(
            f" {reminder.recurrence.get('type')}", ""
        )
    return f"⏰ {reminder.title} — {local:%a %d/%m %H:%M}{rec}"
