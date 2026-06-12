"""Servicio de listas: crear, agregar/marcar ítems, consultar. Todo por lenguaje natural."""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import NotFoundError, ValidationError
from core.events import DomainEvent, get_event_bus
from core.models import List, ListItem, User


def _norm(name: str) -> str:
    return name.strip().lower()


async def get_or_create_list(session: AsyncSession, user: User, name: str) -> tuple[List, bool]:
    if not name.strip():
        raise ValidationError("La lista necesita un nombre.")
    rows = await session.execute(
        select(List).where(List.user_id == user.id, func.lower(List.name) == _norm(name))
    )
    lst = rows.scalar_one_or_none()
    if lst:
        return lst, False
    lst = List(user_id=user.id, name=name.strip())
    session.add(lst)
    await session.flush()
    await get_event_bus().publish(
        DomainEvent(type="list.created", user_id=user.id, payload={"list_id": lst.id})
    )
    return lst, True


async def add_items(session: AsyncSession, user: User, list_name: str, items: list[str]) -> List:
    items = [i.strip() for i in items if i.strip()]
    if not items:
        raise ValidationError("¿Qué querés agregar a la lista?")
    lst, _created = await get_or_create_list(session, user, list_name)
    for content in items:
        session.add(ListItem(list_id=lst.id, content=content))
    await session.flush()
    await get_event_bus().publish(
        DomainEvent(
            type="list.item_added",
            user_id=user.id,
            payload={"list_id": lst.id, "count": len(items)},
        )
    )
    await session.refresh(lst)
    return lst


async def find_list(session: AsyncSession, user: User, name: str) -> List:
    rows = await session.execute(
        select(List).where(List.user_id == user.id, func.lower(List.name) == _norm(name))
    )
    lst = rows.scalar_one_or_none()
    if lst is None:
        rows = await session.execute(
            select(List).where(List.user_id == user.id, List.name.ilike(f"%{name.strip()}%"))
        )
        lst = rows.scalars().first()
    if lst is None:
        raise NotFoundError(f"No tenés ninguna lista que se llame '{name}'.")
    return lst


async def mark_item(session: AsyncSession, user: User, list_name: str, item_query: str) -> ListItem:
    lst = await find_list(session, user, list_name)
    rows = await session.execute(
        select(ListItem)
        .where(
            ListItem.list_id == lst.id,
            ListItem.is_done.is_(False),
            ListItem.content.ilike(f"%{item_query.strip()}%"),
        )
        .limit(1)
    )
    item = rows.scalar_one_or_none()
    if item is None:
        raise NotFoundError(f"No encontré '{item_query}' pendiente en la lista {lst.name}.")
    item.is_done = True
    item.done_at = datetime.now(UTC)
    await session.flush()

    pending = await session.execute(
        select(func.count())
        .select_from(ListItem)
        .where(ListItem.list_id == lst.id, ListItem.is_done.is_(False))
    )
    if pending.scalar_one() == 0:
        await get_event_bus().publish(
            DomainEvent(type="list.completed", user_id=user.id, payload={"list_id": lst.id})
        )
    return item


async def get_all_lists(session: AsyncSession, user: User) -> list[List]:
    rows = await session.execute(
        select(List).where(List.user_id == user.id).order_by(List.created_at)
    )
    return list(rows.scalars())


def format_list(lst: List) -> str:
    lines = [f"📋 *{lst.name}*"]
    for item in lst.items:
        mark = "✅" if item.is_done else "▫️"
        lines.append(f"{mark} {item.content}")
    if len(lines) == 1:
        lines.append("(vacía)")
    return "\n".join(lines)
