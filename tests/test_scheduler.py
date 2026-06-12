"""Scheduler: detección de vencidos, disparo y recurrencia."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import select

from core.models import Reminder
from scheduler.jobs.reminder_fire import fire_due
from scheduler.manager import due_reminders, mark_fired


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append(SimpleNamespace(chat_id=chat_id, text=text, **kwargs))


async def _make_reminder(session, user, minutes_ago: int, recurrence=None) -> Reminder:
    r = Reminder(
        user_id=user.id,
        title="vencido",
        due_at=datetime.now(UTC) - timedelta(minutes=minutes_ago),
        recurrence=recurrence,
    )
    session.add(r)
    await session.flush()
    await session.commit()
    return r


async def test_due_reminders_only_past_and_unfired(session, user):
    past = await _make_reminder(session, user, minutes_ago=5)
    future = Reminder(
        user_id=user.id, title="futuro", due_at=datetime.now(UTC) + timedelta(hours=1)
    )
    session.add(future)
    await session.commit()

    due = await due_reminders(session)
    assert [r.id for r in due] == [past.id]


async def test_mark_fired_recurring_creates_next(session, user):
    r = await _make_reminder(session, user, minutes_ago=1, recurrence={"type": "daily"})
    nxt = await mark_fired(session, r, user)
    assert r.fired_at is not None
    assert r.recurrence is None  # la disparada queda puntual
    assert nxt is not None
    assert nxt.recurrence == {"type": "daily"}
    assert nxt.due_at - r.due_at == timedelta(days=1)


async def test_fire_due_sends_with_keyboard(session, user, db_engine):
    await _make_reminder(session, user, minutes_ago=2)
    bot = FakeBot()
    fired = await fire_due(bot)
    assert fired == 1
    assert bot.sent[0].chat_id == user.telegram_id
    assert "vencido" in bot.sent[0].text
    assert bot.sent[0].reply_markup is not None

    # segunda pasada: no re-dispara
    assert await fire_due(bot) == 0

    rows = await session.execute(select(Reminder).where(Reminder.user_id == user.id))
    assert all(r.fired_at is not None for r in rows.scalars())
