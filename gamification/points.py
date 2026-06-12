"""Catálogo de puntos (valores del brief, a calibrar en beta).

Configurable sin tocar el engine. Eventos que no figuran acá no suman puntos
pero igual cuentan como interacción para la racha.
"""

POINTS: dict[str, int] = {
    "reminder.created": 5,
    "reminder.completed_on_time": 10,
    "reminder.completed_late": 3,
    "list.created": 3,
    "list.completed": 15,
    "memory.saved": 2,
    "calendar.connected": 20,  # una sola vez por usuario
    "daily.interaction": 1,  # primera interacción del día
    "streak.bonus": 25,  # cada 7 días de racha
}

# eventos que se otorgan una única vez por usuario
ONCE_PER_USER = {"calendar.connected"}

STREAK_BONUS_EVERY = 7
