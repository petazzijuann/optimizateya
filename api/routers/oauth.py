"""OAuth de calendarios (Google / Outlook). Tokens SIEMPRE cifrados con Fernet.

El `state` es el user_id interno cifrado con Fernet (firmado + opaco), así el
callback sabe a qué usuario vincular sin exponer ids.
"""

import time
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from aiogram import Bot
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from core.config import get_settings
from core.crypto import decrypt_token, encrypt_token
from core.events import DomainEvent, get_event_bus
from core.logging import get_logger
from core.models import CalendarConnection, User
from domain.calendar_providers import GOOGLE_TOKEN_URL, MS_TOKEN_URL

log = get_logger(__name__)
router = APIRouter()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
MS_AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
GOOGLE_SCOPE = "https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/calendar.readonly"
MS_SCOPE = "offline_access Calendars.ReadWrite"
STATE_TTL_SECONDS = 900

SUCCESS_HTML = """<html><body style="font-family:sans-serif;text-align:center;padding-top:4em">
<h2>✅ ¡Calendario conectado!</h2><p>Ya podés volver a Telegram.</p></body></html>"""


def make_state(user_id: str) -> str:
    return encrypt_token(f"{user_id}|{int(time.time())}").decode()


def parse_state(state: str) -> str:
    try:
        raw = decrypt_token(state.encode())
        user_id, ts = raw.rsplit("|", 1)
        if time.time() - int(ts) > STATE_TTL_SECONDS:
            raise ValueError("expired")
        return user_id
    except Exception as exc:
        raise HTTPException(status_code=400, detail="state inválido o vencido") from exc


def _redirect_uri(provider: str) -> str:
    return f"{get_settings().public_base_url.rstrip('/')}/oauth/{provider}/callback"


@router.get("/oauth/{provider}/connect")
async def oauth_connect(provider: str, state: str) -> RedirectResponse:
    s = get_settings()
    parse_state(state)  # valida antes de redirigir
    if provider == "google":
        params = {
            "client_id": s.google_client_id,
            "redirect_uri": _redirect_uri("google"),
            "response_type": "code",
            "scope": GOOGLE_SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")
    if provider == "outlook":
        params = {
            "client_id": s.ms_client_id,
            "redirect_uri": _redirect_uri("outlook"),
            "response_type": "code",
            "scope": MS_SCOPE,
            "state": state,
        }
        return RedirectResponse(f"{MS_AUTH_URL}?{urlencode(params)}")
    raise HTTPException(status_code=404, detail="proveedor desconocido")


@router.get("/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str,
    state: str,
    session: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    if provider not in ("google", "outlook"):
        raise HTTPException(status_code=404, detail="proveedor desconocido")
    user_id = parse_state(state)
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="usuario inexistente")

    s = get_settings()
    if provider == "google":
        data = {
            "code": code,
            "client_id": s.google_client_id,
            "client_secret": s.google_client_secret,
            "redirect_uri": _redirect_uri("google"),
            "grant_type": "authorization_code",
        }
        token_url = GOOGLE_TOKEN_URL
    else:
        data = {
            "code": code,
            "client_id": s.ms_client_id,
            "client_secret": s.ms_client_secret,
            "redirect_uri": _redirect_uri("outlook"),
            "grant_type": "authorization_code",
            "scope": MS_SCOPE,
        }
        token_url = MS_TOKEN_URL

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(token_url, data=data)
    if resp.status_code != 200:
        log.warning("oauth_exchange_failed", provider=provider, status=resp.status_code)
        raise HTTPException(status_code=400, detail="no se pudo completar la conexión")
    tokens = resp.json()

    provider_key = "google" if provider == "google" else "outlook"
    rows = await session.execute(
        select(CalendarConnection).where(
            CalendarConnection.user_id == user.id, CalendarConnection.provider == provider_key
        )
    )
    conn = rows.scalar_one_or_none()
    expires_at = datetime.now(UTC) + timedelta(seconds=int(tokens.get("expires_in", 3600)))
    if conn is None:
        conn = CalendarConnection(
            user_id=user.id,
            provider=provider_key,
            access_token_enc=encrypt_token(tokens["access_token"]),
            refresh_token_enc=(
                encrypt_token(tokens["refresh_token"]) if tokens.get("refresh_token") else None
            ),
            expires_at=expires_at,
            scope=tokens.get("scope", ""),
        )
        session.add(conn)
    else:
        conn.access_token_enc = encrypt_token(tokens["access_token"])
        if tokens.get("refresh_token"):
            conn.refresh_token_enc = encrypt_token(tokens["refresh_token"])
        conn.expires_at = expires_at
        conn.scope = tokens.get("scope", "")
    await session.flush()

    await get_event_bus().publish(
        DomainEvent(type="calendar.connected", user_id=user.id, payload={"provider": provider_key})
    )

    # avisar por el chat (best-effort)
    try:
        bot = Bot(token=s.telegram_bot_token)
        try:
            await bot.send_message(
                user.telegram_id,
                f"🗓 ¡Calendario de {provider_key.title()} conectado! "
                'Probá: "reunión con Juan el martes 15hs".',
            )
        finally:
            await bot.session.close()
    except Exception:
        log.warning("oauth_notify_failed", provider=provider_key)

    return HTMLResponse(SUCCESS_HTML)
