"""Briefing diario: agenda + recordatorios + racha, en tono conversacional."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import GamificationState, Reminder, User
from domain.calendar import events_for_day


async def build_briefing(session: AsyncSession, user: User) -> str:
    tz = ZoneInfo(user.timezone)
    now_local = datetime.now(tz)
    day_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    day_start_utc = day_start.astimezone(UTC)
    day_end_utc = day_end.astimezone(UTC)

    rows = await session.execute(
        select(Reminder)
        .where(
            Reminder.user_id == user.id,
            Reminder.status == "pending",
            Reminder.due_at >= day_start_utc,
            Reminder.due_at < day_end_utc,
        )
        .order_by(Reminder.due_at)
    )
    reminders = list(rows.scalars())
    events = await events_for_day(session, user, day_start_utc, day_end_utc)
    state = await session.get(GamificationState, user.id)

    lines = [f"🌅 *Buen día{f', {user.first_name}' if user.first_name else ''}!*"]
    lines.append(f"📅 {now_local:%A %d/%m}".capitalize())

    if events:
        lines.append("\n*Agenda de hoy:*")
        for ev in events:
            start = ev.start_at.replace(tzinfo=ev.start_at.tzinfo or UTC).astimezone(tz)
            lines.append(f"🗓 {start:%H:%M} — {ev.title}")
    if reminders:
        lines.append("\n*Recordatorios:*")
        for r in reminders:
            due = r.due_at.replace(tzinfo=r.due_at.tzinfo or UTC).astimezone(tz)
            lines.append(f"⏰ {due:%H:%M} — {r.title}")
    if not events and not reminders:
        lines.append("\nNada agendado para hoy. Día libre para lo que pinte ✨")

    if state and state.current_streak > 0:
        lines.append(f"\n🔥 Racha: *{state.current_streak} días*. ¡Seguila hoy!")
    return "\n".join(lines)
