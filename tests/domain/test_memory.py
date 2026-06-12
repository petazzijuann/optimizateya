"""Memory Bubbles: guardado y recuperación (fallback de texto sin embeddings)."""

from core.events import get_event_bus
from domain import memory


async def test_save_note_and_search_fallback(session, user, no_embeddings):
    events = []

    async def capture(e):
        events.append(e.type)

    get_event_bus().subscribe("*", capture)

    item = await memory.save_note(
        session, user, title="Clave del wifi", content="La clave es FIBER-123"
    )
    assert item.embedding is None  # ollama "caído" → sin vector
    assert "memory.saved" in events

    results = await memory.search(session, user, "wifi")
    assert [r.id for r in results] == [item.id]


async def test_search_isolated_by_user(session, user, no_embeddings):
    from core.models import User

    other = User(telegram_id=777, first_name="Otra", timezone=user.timezone)
    session.add(other)
    await session.flush()
    await memory.save_note(session, user, title="secreto", content="dato privado")
    assert await memory.search(session, other, "secreto") == []


async def test_search_excludes_deleted(session, user, no_embeddings):
    from datetime import UTC, datetime

    item = await memory.save_note(session, user, title="vieja", content="nota vieja")
    item.deleted_at = datetime.now(UTC)
    await session.flush()
    assert await memory.search(session, user, "vieja") == []
