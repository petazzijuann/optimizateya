"""Ejecuta DomainActions del NLU contra los servicios de dominio.

Mantiene la lógica fuera de los handlers del bot. Cada acción devuelve el
texto de respuesta para el usuario (Markdown de Telegram).
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from ai.nlu import DomainAction
from core.errors import DomainError
from core.logging import get_logger, hash_user_id
from core.models import User
from domain import briefing, lists, memory, reminders
from domain import calendar as cal
from domain.dates import parse_natural_datetime

log = get_logger(__name__)


async def execute(session: AsyncSession, user: User, action: DomainAction) -> str:
    try:
        return await _execute(session, user, action)
    except DomainError as exc:
        return str(exc) or "No pude hacer eso 😕"


async def _execute(session: AsyncSession, user: User, action: DomainAction) -> str:
    args = action.arguments
    tool = action.tool
    log.info("action_execute", tool=tool, user=hash_user_id(user.id))

    if tool == "create_reminder":
        r = await reminders.create_reminder(
            session,
            user,
            title=str(args.get("title", "")),
            due_at_natural=str(args.get("due_at_natural", "")),
            recurrence=str(args.get("recurrence", "none")),
        )
        local = r.due_at.replace(tzinfo=r.due_at.tzinfo or UTC).astimezone(ZoneInfo(user.timezone))
        return f"✅ Listo, te recuerdo *{r.title}* el {local:%a %d/%m a las %H:%M}."

    if tool == "list_reminders":
        pending = await reminders.list_pending(session, user)
        if not pending:
            return "No tenés recordatorios pendientes 🎉"
        lines = ["*Tus recordatorios:*"]
        lines += [reminders.format_reminder_line(r, user.timezone) for r in pending]
        return "\n".join(lines)

    if tool == "complete_reminder":
        r = await reminders.find_by_text(session, user, str(args.get("query", "")))
        r = await reminders.complete_reminder(session, user, r)
        nice = "a tiempo 💪" if r.completed_on_time else "(tarde, pero seguro 😉)"
        return f"✅ *{r.title}* cumplido {nice}"

    if tool == "delete_reminder":
        r = await reminders.find_by_text(session, user, str(args.get("query", "")))
        await reminders.cancel_reminder(session, user, r)
        return f"🗑 Cancelé el recordatorio *{r.title}*."

    if tool == "add_list_item":
        items = args.get("items") or []
        if isinstance(items, str):
            items = [items]
        lst = await lists.add_items(session, user, str(args.get("list_name", "")), list(items))
        return f"📋 Agregado a *{lst.name}*:\n" + "\n".join(f"▫️ {i}" for i in items)

    if tool == "mark_list_item":
        item = await lists.mark_item(
            session, user, str(args.get("list_name", "")), str(args.get("item", ""))
        )
        return f"✅ Marcado: {item.content}"

    if tool == "query_list":
        name = str(args.get("list_name", "") or "").strip()
        if name:
            lst = await lists.find_list(session, user, name)
            return lists.format_list(lst)
        all_lists = await lists.get_all_lists(session, user)
        if not all_lists:
            return "Todavía no tenés listas. Decime por ej: 'agregá leche a la lista del súper'."
        return "\n\n".join(lists.format_list(lst) for lst in all_lists)

    if tool == "save_memory":
        mem_item = await memory.save_note(
            session,
            user,
            title=str(args.get("title", "")),
            content=str(args.get("content", "")),
        )
        return f"🫧 Guardado en tu memoria: *{mem_item.title}*"

    if tool == "query_memory":
        results = await memory.search(session, user, str(args.get("query", "")))
        if not results:
            return "No encontré nada de eso en tu memoria 🤔"
        return "*Encontré esto:*\n" + "\n".join(memory.format_memory_line(m) for m in results)

    if tool == "create_event":
        cached, conflicts = await cal.create_event(
            session,
            user,
            title=str(args.get("title", "")),
            start_natural=str(args.get("start_natural", "")),
            duration_minutes=int(args.get("duration_minutes") or 60),
        )
        if cached is None:
            return (
                "⚠️ Tu calendario no responde ahora. Dejé el evento en cola y lo "
                "creo apenas vuelva — te aviso."
            )
        tz = ZoneInfo(user.timezone)
        start = cached.start_at.replace(tzinfo=cached.start_at.tzinfo or UTC).astimezone(tz)
        msg = f"🗓 Evento creado: *{cached.title}* el {start:%a %d/%m a las %H:%M}."
        if conflicts:
            titles = ", ".join(c.title for c in conflicts[:3])
            msg += f"\n⚠️ Ojo: se pisa con {titles}. ¿Querés moverlo?"
        return msg

    if tool == "query_agenda":
        date_natural = str(args.get("date_natural", "") or "").strip()
        tz = ZoneInfo(user.timezone)
        if date_natural and date_natural.lower() not in ("hoy", ""):
            day_local = parse_natural_datetime(date_natural, user.timezone).replace(
                hour=0, minute=0
            )
        else:
            day_local = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
        # reutilizamos el armado del briefing para "hoy"; para otros días, eventos cacheados
        if day_local.date() == datetime.now(tz).date():
            return await briefing.build_briefing(session, user)
        start_utc = day_local.astimezone(UTC)
        events = await cal.events_for_day(session, user, start_utc, start_utc + timedelta(days=1))
        if not events:
            return f"No veo eventos para el {day_local:%a %d/%m} 📭"
        lines = [f"*Agenda del {day_local:%a %d/%m}:*"]
        for ev in events:
            start = ev.start_at.replace(tzinfo=ev.start_at.tzinfo or UTC).astimezone(tz)
            lines.append(f"🗓 {start:%H:%M} — {ev.title}")
        return "\n".join(lines)

    return "Hmm, no sé hacer eso todavía 😅"
