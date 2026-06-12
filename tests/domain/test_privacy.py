"""Privacidad: export completo y hard delete."""

import json

from sqlalchemy import select

from core.models import Reminder, User
from domain import lists, memory, reminders
from domain.privacy import export_user_data, hard_delete_user


async def test_export_contains_all_user_data(session, user, no_embeddings):
    await reminders.create_reminder(session, user, "dentista", "mañana 9am")
    await lists.add_items(session, user, "súper", ["leche"])
    await memory.save_note(session, user, title="wifi", content="FIBER-123")

    raw = await export_user_data(session, user)
    data = json.loads(raw)

    assert data["profile"]["telegram_id"] == user.telegram_id
    assert data["reminders"][0]["title"] == "dentista"
    assert data["lists"][0]["name"] == "súper"
    assert data["memories"][0]["title"] == "wifi"


async def test_hard_delete_removes_everything(session, user, no_embeddings):
    await reminders.create_reminder(session, user, "dentista", "mañana 9am")
    await memory.save_note(session, user, title="wifi", content="FIBER-123")
    uid = user.id

    await hard_delete_user(session, user)
    await session.commit()

    assert await session.get(User, uid) is None
    rows = await session.execute(select(Reminder).where(Reminder.user_id == uid))
    assert list(rows.scalars()) == []
