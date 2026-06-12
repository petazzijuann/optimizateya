"""Listas: creación implícita, ítems, marcado y evento de lista completa."""

import pytest

from core.errors import NotFoundError
from core.events import get_event_bus
from domain import lists


@pytest.fixture
def events_log():
    log = []

    async def capture(event):
        log.append(event.type)

    get_event_bus().subscribe("*", capture)
    return log


async def test_add_items_creates_list(session, user, events_log):
    lst = await lists.add_items(session, user, "súper", ["leche", "pan"])
    assert lst.name == "súper"
    assert {i.content for i in lst.items} == {"leche", "pan"}
    assert "list.created" in events_log
    assert "list.item_added" in events_log


async def test_add_to_existing_list_no_duplicate(session, user, events_log):
    await lists.add_items(session, user, "súper", ["leche"])
    await lists.add_items(session, user, "Súper", ["pan"])  # case-insensitive
    all_lists = await lists.get_all_lists(session, user)
    assert len(all_lists) == 1
    assert events_log.count("list.created") == 1


async def test_mark_item_and_complete_event(session, user, events_log):
    await lists.add_items(session, user, "farmacia", ["ibuprofeno", "curitas"])
    await lists.mark_item(session, user, "farmacia", "ibupro")
    assert "list.completed" not in events_log
    await lists.mark_item(session, user, "farmacia", "curitas")
    assert "list.completed" in events_log


async def test_mark_missing_item(session, user):
    await lists.add_items(session, user, "súper", ["leche"])
    with pytest.raises(NotFoundError):
        await lists.mark_item(session, user, "súper", "caviar")


async def test_format_list(session, user):
    lst = await lists.add_items(session, user, "súper", ["leche"])
    text = lists.format_list(lst)
    assert "súper" in text and "leche" in text
