"""Comandos de gamificación: /puntos /racha /ranking /stats /logros /historial."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import func, select

from core.models import GamificationState, PointEvent, User, UserAchievement
from gamification import leaderboard
from gamification.catalog import CATALOG

router = Router(name="gamification")

EVENT_LABELS = {
    "reminder.created": "Recordatorio creado",
    "reminder.completed_on_time": "Recordatorio cumplido a tiempo",
    "reminder.completed_late": "Recordatorio cumplido (tarde)",
    "list.created": "Lista creada",
    "list.completed": "Lista completada",
    "memory.saved": "Guardado en memoria",
    "calendar.connected": "Calendario conectado",
    "daily.interaction": "Uso diario",
    "streak.bonus": "Bonus de racha 🔥",
}


def _label(event_type: str) -> str:
    if event_type.startswith("achievement."):
        code = event_type.removeprefix("achievement.")
        for ach in CATALOG:
            if ach.code == code:
                return f"Logro: {ach.name} 🏅"
        return "Logro desbloqueado 🏅"
    return EVENT_LABELS.get(event_type, event_type)


async def _state(session, user) -> GamificationState:
    state = await session.get(GamificationState, user.id)
    return state or GamificationState(user_id=user.id)


@router.message(Command("puntos"))
async def cmd_puntos(message: Message, user, session) -> None:
    state = await _state(session, user)
    rows = await session.execute(
        select(PointEvent)
        .where(PointEvent.user_id == user.id)
        .order_by(PointEvent.created_at.desc())
        .limit(3)
    )
    recent = list(rows.scalars())
    text = f"🏆 Tenés *{state.total_points} puntos*."
    if recent:
        text += "\n\nÚltimos sumados:\n" + "\n".join(
            f"+{p.points} — {_label(p.event_type)}" for p in recent
        )
    await message.answer(text)


@router.message(Command("racha"))
async def cmd_racha(message: Message, user, session) -> None:
    state = await _state(session, user)
    if state.current_streak == 0:
        await message.answer("Todavía no arrancaste tu racha 🔥 ¡Hacé algo hoy y empezala!")
        return
    await message.answer(
        f"🔥 Racha actual: *{state.current_streak} días*\n"
        f"🥇 Récord histórico: *{state.longest_streak} días*"
    )


@router.message(Command("ranking"))
async def cmd_ranking(message: Message, user, session) -> None:
    top = await leaderboard.top(10)
    my_rank = await leaderboard.rank(user.id)
    total = await leaderboard.total_players()
    lines = ["🏁 *Ranking global*"]
    if top:
        ids = [uid for uid, _ in top]
        rows = await session.execute(select(User.id, User.first_name).where(User.id.in_(ids)))
        names = dict(rows.all())
        medals = ["🥇", "🥈", "🥉"] + ["▪️"] * 7
        for i, (uid, score) in enumerate(top):
            name = "Vos" if uid == user.id else (names.get(uid) or "Anónimo")
            lines.append(f"{medals[i]} {name} — {score} pts")
    else:
        lines.append("Todavía no hay nadie en el ranking. ¡Sé el primero!")
    if my_rank:
        lines.append(f"\nVas *{my_rank}°* de {total} 💪")
    elif user.leaderboard_opt_out:
        lines.append("\n(Estás fuera del ranking por elección — privacidad ante todo)")
    await message.answer("\n".join(lines))


@router.message(Command("stats"))
async def cmd_stats(message: Message, user, session) -> None:
    state = await _state(session, user)

    async def _count(*types: str) -> int:
        rows = await session.execute(
            select(func.count())
            .select_from(PointEvent)
            .where(PointEvent.user_id == user.id, PointEvent.event_type.in_(types))
        )
        return rows.scalar_one()

    on_time = await _count("reminder.completed_on_time")
    late = await _count("reminder.completed_late")
    created = await _count("reminder.created")
    achievements = await session.execute(
        select(func.count())
        .select_from(UserAchievement)
        .where(UserAchievement.user_id == user.id)
    )
    n_ach = achievements.scalar_one()
    done = on_time + late
    pct = round(100 * done / created) if created else 0
    await message.answer(
        "📊 *Tus estadísticas*\n"
        f"🏆 Puntos: {state.total_points}\n"
        f"🔥 Racha: {state.current_streak} días (récord {state.longest_streak})\n"
        f"⏰ Recordatorios: {created} creados, {done} cumplidos ({pct}%)\n"
        f"🏅 Logros: {n_ach}/{len(CATALOG)}"
    )


@router.message(Command("logros"))
async def cmd_logros(message: Message, user, session) -> None:
    rows = await session.execute(
        select(UserAchievement.achievement_code).where(UserAchievement.user_id == user.id)
    )
    unlocked = {code for (code,) in rows}
    lines = ["🏅 *Tus logros*"]
    for ach in CATALOG:
        mark = "✅" if ach.code in unlocked else "🔒"
        lines.append(f"{mark} *{ach.name}* — {ach.description} (+{ach.points})")
    await message.answer("\n".join(lines))


@router.message(Command("historial"))
async def cmd_historial(message: Message, user, session) -> None:
    rows = await session.execute(
        select(PointEvent)
        .where(PointEvent.user_id == user.id)
        .order_by(PointEvent.created_at.desc())
        .limit(10)
    )
    events = list(rows.scalars())
    if not events:
        await message.answer("Todavía no hay actividad. ¡Creá tu primer recordatorio! ⏰")
        return
    lines = ["🧾 *Última actividad*"]
    for p in events:
        lines.append(f"+{p.points} — {_label(p.event_type)} ({p.created_at:%d/%m %H:%M})")
    await message.answer("\n".join(lines))
