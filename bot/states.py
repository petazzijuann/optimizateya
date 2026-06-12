"""Estados del FSM de onboarding."""

from aiogram.fsm.state import State, StatesGroup


class Onboarding(StatesGroup):
    choosing_timezone = State()
    typing_timezone = State()
    choosing_briefing_hour = State()
