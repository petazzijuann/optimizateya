"""Cálculo de racha por día calendario en la timezone del usuario."""

from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from core.models import GamificationState

TouchResult = Literal["same_day", "continued", "reset", "started"]


def today_for(timezone: str, now: datetime | None = None) -> date:
    tz = ZoneInfo(timezone)
    return (now.astimezone(tz) if now else datetime.now(tz)).date()


def touch(state: GamificationState, today: date) -> TouchResult:
    """Registra actividad de hoy y actualiza la racha. Idempotente dentro del día."""
    last = state.last_active_date
    if last == today:
        return "same_day"
    if last == today - timedelta(days=1):
        state.current_streak += 1
        result: TouchResult = "continued"
    elif last is None:
        state.current_streak = 1
        result = "started"
    else:
        state.current_streak = 1
        result = "reset"
    state.last_active_date = today
    state.longest_streak = max(state.longest_streak, state.current_streak)
    return result
