"""Gestión de recordatorios vencidos: la DB es la fuente de verdad.

El scheduler consulta cada ~30 s los `reminders` con `due_at` vencido y sin
disparar (`fired_at IS NULL`). Para recurrentes, al disparar se crea la
próxima ocurrencia como fila nueva (la disparada queda esperando "hecho").
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Reminder, User
from domain.reminders import next_occurrence


async def due_reminders(session: AsyncSession, now: datetime | None = None) -> list[Reminder]:
    now = now or datetime.now(UTC)
    rows = await session.execute(
        select(Reminder)
        .where(
            Reminder.status == "pending",
            Reminder.fired_at.is_(None),
            Reminder.due_at <= now,
        )
        .order_by(Reminder.due_at)
        .limit(100)
    )
    return list(rows.scalars())


async def mark_fired(session: AsyncSession, reminder: Reminder, user: User) -> Reminder | None:
    """Marca como disparado y, si recurre, crea la próxima ocurrencia."""
    reminder.fired_at = datetime.now(UTC)
    nxt = next_occurrence(reminder, user.timezone)
    next_reminder = None
    if nxt is not None:
        next_reminder = Reminder(
            user_id=reminder.user_id,
            title=reminder.title,
            due_at=nxt,
            recurrence=reminder.recurrence,
        )
        session.add(next_reminder)
        reminder.recurrence = None  # la fila disparada pasa a ser puntual
    await session.flush()
    return next_reminder
