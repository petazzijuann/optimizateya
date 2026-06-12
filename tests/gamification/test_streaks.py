"""Racha: transiciones por día calendario."""

from datetime import date

from core.models import GamificationState
from gamification.streaks import touch


def _state(**kwargs) -> GamificationState:
    defaults = {"user_id": "u1", "total_points": 0, "current_streak": 0, "longest_streak": 0}
    defaults.update(kwargs)
    return GamificationState(**defaults)


def test_first_touch_starts_streak():
    s = _state()
    assert touch(s, date(2026, 6, 10)) == "started"
    assert s.current_streak == 1
    assert s.longest_streak == 1


def test_same_day_idempotent():
    s = _state(current_streak=3, longest_streak=3, last_active_date=date(2026, 6, 10))
    assert touch(s, date(2026, 6, 10)) == "same_day"
    assert s.current_streak == 3


def test_consecutive_day_continues():
    s = _state(current_streak=3, longest_streak=5, last_active_date=date(2026, 6, 10))
    assert touch(s, date(2026, 6, 11)) == "continued"
    assert s.current_streak == 4
    assert s.longest_streak == 5


def test_gap_resets():
    s = _state(current_streak=9, longest_streak=9, last_active_date=date(2026, 6, 10))
    assert touch(s, date(2026, 6, 13)) == "reset"
    assert s.current_streak == 1
    assert s.longest_streak == 9  # récord se conserva
