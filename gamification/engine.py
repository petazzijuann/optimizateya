"""Motor de gamificación: consume eventos de dominio y aplica puntos/racha/logros.

Subsistema independiente: se suscribe al event bus con wildcard y NUNCA es
llamado directamente por el dominio. Abre su propia sesión de DB.
"""

from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import session_scope
from core.events import WILDCARD, DomainEvent, EventBus, get_event_bus
from core.logging import get_logger, hash_user_id
from core.models import Achievement, GamificationState, PointEvent, User
from core.redis import get_redis
from gamification import leaderboard, streaks
from gamification.achievements import EARLY_COUNTER_KEY, evaluate
from gamification.catalog import CATALOG
from gamification.points import ONCE_PER_USER, POINTS, STREAK_BONUS_EVERY

log = get_logger(__name__)

EARLY_HOUR = 8

# eventos internos del propio engine: jamás reprocesarlos
_INTERNAL_PREFIXES = ("daily.", "streak.", "achievement.")


async def handle_event(event: DomainEvent) -> None:
    if event.type.startswith(_INTERNAL_PREFIXES):
        return
    async with session_scope() as session:
        await _process(session, event)


async def _process(session: AsyncSession, event: DomainEvent) -> None:
    user = await session.get(User, event.user_id)
    if user is None or user.deleted_at is not None:
        return

    state = await session.get(GamificationState, user.id)
    if state is None:
        state = GamificationState(user_id=user.id)
        session.add(state)
        await session.flush()

    awarded = 0

    # 1) racha + punto de uso diario
    today = streaks.today_for(user.timezone, event.occurred_at)
    touch = streaks.touch(state, today)
    if touch != "same_day":
        awarded += await _award(session, state, "daily.interaction", POINTS["daily.interaction"])
        if (
            touch == "continued"
            and state.current_streak > 0
            and state.current_streak % STREAK_BONUS_EVERY == 0
        ):
            awarded += await _award(session, state, "streak.bonus", POINTS["streak.bonus"])

    # 2) puntos del evento en sí
    pts = POINTS.get(event.type, 0)
    already = event.type in ONCE_PER_USER and await _already_awarded(
        session, user.id, event.type
    )
    if pts and not already:
        ref = event.payload.get("reminder_id") or event.payload.get("memory_id")
        awarded += await _award(session, state, event.type, pts, ref_id=ref)

    # 3) contador "madrugador" (cumplido antes de las 8 AM hora local)
    if event.type.startswith("reminder.completed"):
        local_hour = event.occurred_at.astimezone(ZoneInfo(user.timezone)).hour
        if local_hour < EARLY_HOUR:
            await get_redis().incr(EARLY_COUNTER_KEY.format(user_id=user.id))

    # 4) logros
    for ach in await evaluate(session, user.id):
        awarded += await _award(session, state, f"achievement.{ach.code}", ach.points)
        log.info("achievement_unlocked", user=hash_user_id(user.id), code=ach.code)

    # 5) leaderboard (Redis ZSET), respetando opt-out
    if awarded and not user.leaderboard_opt_out:
        await leaderboard.incr(user.id, awarded)

    log.info(
        "gamification_applied",
        user=hash_user_id(user.id),
        event_type=event.type,
        points=awarded,
        streak=state.current_streak,
    )


async def _award(
    session: AsyncSession,
    state: GamificationState,
    event_type: str,
    points: int,
    ref_id: str | None = None,
) -> int:
    session.add(
        PointEvent(user_id=state.user_id, event_type=event_type, points=points, ref_id=ref_id)
    )
    state.total_points += points
    await session.flush()
    return points


async def _already_awarded(session: AsyncSession, user_id: str, event_type: str) -> bool:
    rows = await session.execute(
        select(func.count())
        .select_from(PointEvent)
        .where(PointEvent.user_id == user_id, PointEvent.event_type == event_type)
    )
    return rows.scalar_one() > 0


async def seed_achievements(session: AsyncSession) -> None:
    """Siembra/actualiza el catálogo de logros en la tabla achievements."""
    is_postgres = session.bind is not None and session.bind.dialect.name == "postgresql"
    for ach in CATALOG:
        if is_postgres:
            stmt = (
                pg_insert(Achievement)
                .values(
                    code=ach.code, name=ach.name, description=ach.description, points=ach.points
                )
                .on_conflict_do_update(
                    index_elements=[Achievement.code],
                    set_={"name": ach.name, "description": ach.description, "points": ach.points},
                )
            )
            await session.execute(stmt)
        else:
            existing = await session.get(Achievement, ach.code)
            if existing is None:
                session.add(
                    Achievement(
                        code=ach.code,
                        name=ach.name,
                        description=ach.description,
                        points=ach.points,
                    )
                )
    await session.flush()


def register(bus: EventBus | None = None) -> None:
    """Suscribe el engine al event bus. Llamar una vez por proceso al boot."""
    (bus or get_event_bus()).subscribe(WILDCARD, handle_event)
