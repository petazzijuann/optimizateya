"""Servicio de recordatorios: creación, cumplimiento, recurrencia, cancelación."""

from datetime import UTC, datetime, timedelta

import pytest

from core.errors import DateParseError, NotFoundError
from core.events import get_event_bus
from domain import reminders


@pytest.fixture
def events_log():
    log = []

    async def capture(event):
        log.append(event)

    get_event_bus().subscribe("*", capture)
    return log


async def test_create_reminder_emits_event(session, user, events_log):
    r = await reminders.create_reminder(session, user, "comprar pan", "mañana 9am")
    assert r.status == "pending"
    assert r.due_at.tzinfo is not None
    assert [e.type for e in events_log] == ["reminder.created"]
    assert events_log[0].user_id == user.id


async def test_create_reminder_bad_date(session, user):
    with pytest.raises(DateParseError):
        await reminders.create_reminder(session, user, "algo", "ni idea cuándo")


async def test_complete_on_time(session, user, events_log):
    r = await reminders.create_reminder(session, user, "llamar al médico", "en 2 horas")
    r = await reminders.complete_reminder(session, user, r)
    assert r.status == "done"
    assert r.completed_on_time is True
    assert "reminder.completed_on_time" in [e.type for e in events_log]


async def test_complete_late(session, user, events_log):
    r = await reminders.create_reminder(session, user, "sacar la basura", "en 1 hora")
    late = datetime.now(UTC) + timedelta(hours=3)
    r = await reminders.complete_reminder(session, user, r, when=late)
    assert r.completed_on_time is False
    assert "reminder.completed_late" in [e.type for e in events_log]


async def test_find_by_text_and_cancel(session, user):
    await reminders.create_reminder(session, user, "regar las plantas", "mañana")
    r = await reminders.find_by_text(session, user, "plantas")
    await reminders.cancel_reminder(session, user, r)
    assert r.status == "cancelled"
    with pytest.raises(NotFoundError):
        await reminders.find_by_text(session, user, "plantas")


async def test_next_occurrence_daily_weekly_monthly(session, user):
    r = await reminders.create_reminder(session, user, "gym", "mañana 8am", recurrence="daily")
    nxt = reminders.next_occurrence(r, user.timezone)
    assert nxt is not None
    assert nxt - r.due_at == timedelta(days=1)

    r.recurrence = {"type": "weekly"}
    weekly = reminders.next_occurrence(r, user.timezone)
    assert weekly is not None
    assert weekly - r.due_at == timedelta(weeks=1)

    r.recurrence = None
    assert reminders.next_occurrence(r, user.timezone) is None


async def test_user_isolation(session, user):
    from core.models import User

    other = User(telegram_id=999, first_name="Otro", timezone=user.timezone)
    session.add(other)
    await session.flush()
    await reminders.create_reminder(session, user, "privado", "mañana")
    assert await reminders.list_pending(session, other) == []
    with pytest.raises(NotFoundError):
        await reminders.find_by_text(session, other, "privado")
