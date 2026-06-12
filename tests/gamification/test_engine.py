"""Engine de gamificación end-to-end con event bus + fakeredis."""

from sqlalchemy import select

from core.events import DomainEvent, get_event_bus
from core.models import GamificationState, PointEvent, UserAchievement
from gamification import leaderboard
from gamification.engine import register, seed_achievements


async def _publish(event_type: str, user_id: str, payload: dict | None = None):
    await get_event_bus().publish(
        DomainEvent(type=event_type, user_id=user_id, payload=payload or {})
    )


async def test_reminder_created_awards_points(session, user, redis):
    await seed_achievements(session)
    await session.commit()
    register()

    await _publish("reminder.created", user.id, {"reminder_id": None})

    state = await session.get(GamificationState, user.id)
    await session.refresh(state)
    # +5 (reminder.created) +1 (primera interacción del día)
    assert state.total_points == 6
    assert state.current_streak == 1
    assert await leaderboard.rank(user.id) == 1


async def test_calendar_connected_only_once(session, user, redis):
    await seed_achievements(session)
    await session.commit()
    register()

    await _publish("calendar.connected", user.id)
    await _publish("calendar.connected", user.id)

    rows = await session.execute(
        select(PointEvent).where(
            PointEvent.user_id == user.id, PointEvent.event_type == "calendar.connected"
        )
    )
    assert len(list(rows.scalars())) == 1


async def test_first_memory_unlocks_achievement(session, user, redis):
    await seed_achievements(session)
    await session.commit()
    register()

    await _publish("memory.saved", user.id, {"memory_id": None})

    rows = await session.execute(
        select(UserAchievement).where(UserAchievement.user_id == user.id)
    )
    codes = [ua.achievement_code for ua in rows.scalars()]
    assert "primera_memoria" in codes

    state = await session.get(GamificationState, user.id)
    await session.refresh(state)
    # +2 memoria +1 diario +10 logro
    assert state.total_points == 13


async def test_opt_out_excluded_from_leaderboard(session, user, redis):
    user.leaderboard_opt_out = True
    await session.commit()
    await seed_achievements(session)
    await session.commit()
    register()

    await _publish("reminder.created", user.id)
    assert await leaderboard.rank(user.id) is None
    state = await session.get(GamificationState, user.id)
    await session.refresh(state)
    assert state.total_points > 0  # los puntos igual se acumulan


async def test_leaderboard_ops(redis):
    await leaderboard.incr("a", 10)
    await leaderboard.incr("b", 30)
    await leaderboard.incr("a", 5)
    assert await leaderboard.rank("b") == 1
    assert await leaderboard.rank("a") == 2
    assert await leaderboard.top(2) == [("b", 30), ("a", 15)]
    assert await leaderboard.total_players() == 2
    await leaderboard.remove("b")
    assert await leaderboard.rank("a") == 1
