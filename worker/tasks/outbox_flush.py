"""Reintento de acciones encoladas contra servicios externos caídos (modo offline)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from core.errors import DomainError, ExternalServiceError
from core.logging import get_logger, hash_user_id
from core.models import CalendarEventCache, OutboxAction, User
from worker.tasks.common import session_scope

log = get_logger(__name__)

MAX_ATTEMPTS = 8


async def outbox_flush(ctx) -> int:
    """Procesa acciones pendientes vencidas. Corre como cron cada minuto."""
    bot = ctx.get("bot")
    now = datetime.now(UTC)
    processed = 0
    async with session_scope() as session:
        rows = await session.execute(
            select(OutboxAction)
            .where(OutboxAction.status == "pending", OutboxAction.next_retry_at <= now)
            .limit(20)
        )
        for action in rows.scalars():
            processed += 1
            try:
                await _execute(session, action, bot)
                action.status = "done"
            except ExternalServiceError:
                action.attempts += 1
                if action.attempts >= MAX_ATTEMPTS:
                    action.status = "failed"
                    await _notify(
                        bot,
                        session,
                        action,
                        "❌ No pude crear el evento — el calendario sigue caído. "
                        "Probá de nuevo más tarde.",
                    )
                else:
                    # backoff exponencial: 2, 4, 8... minutos
                    action.next_retry_at = now + timedelta(minutes=2**action.attempts)
            except DomainError:
                action.status = "failed"
                log.warning("outbox_action_invalid", action_type=action.action_type)
    return processed


async def _execute(session, action: OutboxAction, bot) -> None:
    if action.action_type == "calendar.create_event":
        from domain import calendar_providers as providers
        from domain.calendar import _fresh_access_token, get_connection

        user = await session.get(User, action.user_id)
        if user is None:
            raise DomainError("usuario inexistente")
        conn = await get_connection(session, user)
        token = await _fresh_access_token(session, conn)
        payload = action.payload
        start_at = datetime.fromisoformat(payload["start_at"])
        end_at = datetime.fromisoformat(payload["end_at"])
        result = await providers.create_event(
            conn.provider, token, payload["title"], start_at, end_at
        )
        session.add(
            CalendarEventCache(
                user_id=user.id,
                provider=conn.provider,
                external_id=result["external_id"],
                title=payload["title"],
                start_at=start_at,
                end_at=end_at,
            )
        )
        await _notify(
            bot,
            session,
            action,
            f"🗓 ¡Volvió el calendario! Creé el evento *{payload['title']}*.",
        )
        log.info("outbox_flushed", user=hash_user_id(user.id), action=action.action_type)
    else:
        raise DomainError(f"acción desconocida: {action.action_type}")


async def _notify(bot, session, action: OutboxAction, text: str) -> None:
    if bot is None:
        return
    user = await session.get(User, action.user_id)
    if user is None:
        return
    try:
        await bot.send_message(user.telegram_id, text)
    except Exception:
        log.warning("outbox_notify_failed")
