"""Modelos SQLAlchemy. Importar todos acá garantiza que Base.metadata esté completa."""

from core.models.achievement import Achievement, UserAchievement
from core.models.base import Base
from core.models.calendar import CalendarConnection, CalendarEventCache
from core.models.feature_flag import FeatureFlag
from core.models.gamification import GamificationState, PointEvent
from core.models.list import List, ListItem
from core.models.memory import EMBEDDING_DIMS, MemoryItem
from core.models.outbox import OutboxAction
from core.models.reminder import Reminder
from core.models.user import User

__all__ = [
    "EMBEDDING_DIMS",
    "Achievement",
    "Base",
    "CalendarConnection",
    "CalendarEventCache",
    "FeatureFlag",
    "GamificationState",
    "List",
    "ListItem",
    "MemoryItem",
    "OutboxAction",
    "PointEvent",
    "Reminder",
    "User",
    "UserAchievement",
]
