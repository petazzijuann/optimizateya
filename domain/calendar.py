"""Servicio de calendario: eventos por lenguaje natural, conflictos, modo offline.

Tokens OAuth viven cifrados (Fernet) en calendar_connections; acá se descifran
solo en memoria para llamar a la API. Si el proveedor está caído, la acción va
a outbox_actions y el worker la reintenta (modo offline).
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.crypto import decrypt_token, encrypt_token
from core.errors import CalendarNotConnectedError, ExternalServiceError
from core.events import DomainEvent, get_event_bus
from core.logging import get_logger
from core.models import CalendarConnection, CalendarEventCache, OutboxAction, User
from domain import calendar_providers as providers
from domain.dates import parse_natural_datetime

log = get_logger(__name__)

DEFAULT_DURATION_MIN = 60


async def get_connection(session: AsyncSession, user: User) -> CalendarConnection:
    rows = await session.execute(
        select(CalendarConnection).where(CalendarConnection.user_id == user.id)
    )
    conn = rows.scalars().first()
    if conn is None:
        raise CalendarNotConnectedError(
            "Todavía no conectaste ningún calendario. Usá /calendario para vincular "
            "Google u Outlook."
        )
    return conn


async def _fresh_access_token(session: AsyncSession, conn: CalendarConnection) -> str:
    """Descifra el access token; si expiró, lo renueva y re-cifra."""
    now = datetime.now(UTC)
    if conn.expires_at and conn.expires_at.replace(tzinfo=UTC) > now + timedelta(minutes=2):
        return decrypt_token(conn.access_token_enc)
    if conn.refresh_token_enc is None:
        return decrypt_token(conn.access_token_enc)
    data = await providers.refresh_access_token(
        conn.provider, decrypt_token(conn.refresh_token_enc)
    )
    conn.access_token_enc = encrypt_token(data["access_token"])
    if data.get("refresh_token"):
        conn.refresh_token_enc = encrypt_token(data["refresh_token"])
    conn.expires_at = now + timedelta(seconds=int(data.get("expires_in", 3600)))
    await session.flush()
    return data["access_token"]


async def find_conflicts(
    session: AsyncSession, user: User, start_at: datetime, end_at: datetime
) -> list[CalendarEventCache]:
    rows = await session.execute(
        select(CalendarEventCache).where(
            CalendarEventCache.user_id == user.id,
            CalendarEventCache.start_at < end_at,
            CalendarEventCache.end_at > start_at,
        )
    )
    return list(rows.scalars())


async def create_event(
    session: AsyncSession,
    user: User,
    title: str,
    start_natural: str,
    duration_minutes: int = DEFAULT_DURATION_MIN,
) -> tuple[CalendarEventCache | None, list[CalendarEventCache]]:
    """Crea el evento. Devuelve (evento_cacheado | None si fue a outbox, conflictos)."""
    conn = await get_connection(session, user)
    start_local = parse_natural_datetime(start_natural, user.timezone)
    start_at = start_local.astimezone(UTC)
    end_at = start_at + timedelta(minutes=duration_minutes or DEFAULT_DURATION_MIN)

    conflicts = await find_conflicts(session, user, start_at, end_at)

    try:
        token = await _fresh_access_token(session, conn)
        result = await providers.create_event(conn.provider, token, title, start_at, end_at)
    except ExternalServiceError:
        # modo offline: encolar en outbox y avisar
        session.add(
            OutboxAction(
                user_id=user.id,
                action_type="calendar.create_event",
                payload={
                    "title": title,
                    "start_at": start_at.isoformat(),
                    "end_at": end_at.isoformat(),
                },
                next_retry_at=datetime.now(UTC) + timedelta(minutes=2),
            )
        )
        await session.flush()
        log.info("calendar_event_queued_offline", provider=conn.provider)
        return None, conflicts

    cached = CalendarEventCache(
        user_id=user.id,
        provider=conn.provider,
        external_id=result["external_id"],
        title=title,
        start_at=start_at,
        end_at=end_at,
    )
    session.add(cached)
    await session.flush()
    await get_event_bus().publish(
        DomainEvent(
            type="calendar.event_created", user_id=user.id, payload={"event_id": cached.id}
        )
    )
    return cached, conflicts


async def sync_events(session: AsyncSession, user: User, days: int = 7) -> int:
    """Reconciliación: trae eventos del proveedor al cache local. Devuelve cuántos."""
    conn = await get_connection(session, user)
    token = await _fresh_access_token(session, conn)
    now = datetime.now(UTC)
    events = await providers.list_events(conn.provider, token, now, now + timedelta(days=days))
    for ev in events:
        rows = await session.execute(
            select(CalendarEventCache).where(
                CalendarEventCache.user_id == user.id,
                CalendarEventCache.provider == conn.provider,
                CalendarEventCache.external_id == ev["external_id"],
            )
        )
        cached = rows.scalar_one_or_none()
        if cached:
            cached.title = ev["title"]
            cached.start_at = ev["start_at"]
            cached.end_at = ev["end_at"]
        else:
            session.add(
                CalendarEventCache(
                    user_id=user.id,
                    provider=conn.provider,
                    external_id=ev["external_id"],
                    title=ev["title"],
                    start_at=ev["start_at"],
                    end_at=ev["end_at"],
                )
            )
    await session.flush()
    return len(events)


async def events_for_day(
    session: AsyncSession, user: User, day_start: datetime, day_end: datetime
) -> list[CalendarEventCache]:
    rows = await session.execute(
        select(CalendarEventCache)
        .where(
            CalendarEventCache.user_id == user.id,
            CalendarEventCache.start_at >= day_start,
            CalendarEventCache.start_at < day_end,
        )
        .order_by(CalendarEventCache.start_at)
    )
    return list(rows.scalars())
