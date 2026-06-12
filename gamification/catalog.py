"""Definición declarativa de logros.

Cada logro tiene una condición sobre `AchievementStats` (números ya agregados);
el evaluador no sabe de SQL ni de Redis.
"""

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class AchievementStats:
    memories_saved: int = 0
    reminders_completed: int = 0
    early_completions: int = 0  # cumplidos antes de las 8 AM hora local
    current_streak: int = 0


@dataclass(frozen=True)
class AchievementDef:
    code: str
    name: str
    description: str
    points: int
    condition: Callable[[AchievementStats], bool]


CATALOG: list[AchievementDef] = [
    AchievementDef(
        code="primera_memoria",
        name="Primera memoria",
        description="Guardaste tu primer archivo o nota",
        points=10,
        condition=lambda s: s.memories_saved >= 1,
    ),
    AchievementDef(
        code="semana_perfecta",
        name="Semana perfecta",
        description="7 días seguidos de actividad cumpliendo tus recordatorios",
        points=50,
        condition=lambda s: s.current_streak >= 7,
    ),
    AchievementDef(
        code="centurion",
        name="Centurión",
        description="100 recordatorios cumplidos",
        points=100,
        condition=lambda s: s.reminders_completed >= 100,
    ),
    AchievementDef(
        code="madrugador",
        name="Madrugador",
        description="Cumpliste un recordatorio antes de las 8 AM, 5 veces",
        points=30,
        condition=lambda s: s.early_completions >= 5,
    ),
    AchievementDef(
        code="cerebro_maestro",
        name="Cerebro maestro",
        description="50 elementos guardados en tu memoria",
        points=75,
        condition=lambda s: s.memories_saved >= 50,
    ),
]
