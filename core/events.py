"""Event bus in-process (publish/subscribe).

El dominio emite eventos; la gamificación (y quien quiera) se suscribe.
La interfaz es async y desacoplada: mañana puede respaldarse en Redis Streams
sin tocar a los emisores. Un handler que falla NUNCA rompe el flujo principal.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger, hash_user_id

log = get_logger(__name__)

WILDCARD = "*"


@dataclass(frozen=True)
class DomainEvent:
    type: str  # ej. "reminder.completed_on_time"
    user_id: str  # UUID interno del usuario
    payload: dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


Handler = Callable[[DomainEvent], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Handler]] = {}

    def subscribe(self, event_type: str, handler: Handler) -> None:
        """Suscribe a un tipo exacto o a WILDCARD ("*") para todos."""
        self._subscribers.setdefault(event_type, []).append(handler)

    async def publish(self, event: DomainEvent) -> None:
        handlers = [
            *self._subscribers.get(event.type, []),
            *self._subscribers.get(WILDCARD, []),
        ]
        for handler in handlers:
            try:
                await handler(event)
            except Exception:
                # La gamificación (u otro suscriptor) jamás rompe el dominio.
                log.exception(
                    "event_handler_failed",
                    event_type=event.type,
                    user=hash_user_id(event.user_id),
                    handler=getattr(handler, "__qualname__", repr(handler)),
                )

    def clear(self) -> None:
        self._subscribers.clear()


_bus = EventBus()


def get_event_bus() -> EventBus:
    return _bus
