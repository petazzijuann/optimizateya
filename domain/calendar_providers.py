"""Clientes REST async (httpx) para Google Calendar y Microsoft Graph.

Se usa REST directo en lugar de los SDKs oficiales (sync) para no bloquear
el event loop. Tokens SIEMPRE llegan ya descifrados desde domain/calendar.py.
"""

from datetime import UTC, datetime
from typing import Any

import httpx

from core.config import get_settings
from core.errors import ExternalServiceError

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
MS_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
MS_EVENTS_URL = "https://graph.microsoft.com/v1.0/me/events"
MS_CALENDARVIEW_URL = "https://graph.microsoft.com/v1.0/me/calendarview"

_TIMEOUT = 15.0


async def refresh_access_token(provider: str, refresh_token: str) -> dict[str, Any]:
    """Devuelve {access_token, expires_in, refresh_token?}."""
    s = get_settings()
    if provider == "google":
        data = {
            "client_id": s.google_client_id,
            "client_secret": s.google_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        url = GOOGLE_TOKEN_URL
    else:
        data = {
            "client_id": s.ms_client_id,
            "client_secret": s.ms_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
            "scope": "offline_access Calendars.ReadWrite",
        }
        url = MS_TOKEN_URL
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(url, data=data)
    if resp.status_code != 200:
        raise ExternalServiceError(f"No pude renovar la sesión de {provider}.")
    return resp.json()


async def create_event(
    provider: str,
    access_token: str,
    title: str,
    start_at: datetime,
    end_at: datetime,
) -> dict[str, Any]:
    """Crea el evento y devuelve {external_id}."""
    headers = {"Authorization": f"Bearer {access_token}"}
    if provider == "google":
        body = {
            "summary": title,
            "start": {"dateTime": start_at.astimezone(UTC).isoformat()},
            "end": {"dateTime": end_at.astimezone(UTC).isoformat()},
        }
        url = GOOGLE_EVENTS_URL
    else:
        body = {
            "subject": title,
            "start": {
                "dateTime": start_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": end_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": "UTC",
            },
        }
        url = MS_EVENTS_URL
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, json=body)
    except httpx.HTTPError as exc:
        raise ExternalServiceError(f"{provider} no responde.") from exc
    if resp.status_code >= 500:
        raise ExternalServiceError(f"{provider} está caído.")
    if resp.status_code not in (200, 201):
        raise ExternalServiceError(f"{provider} rechazó el evento ({resp.status_code}).")
    data = resp.json()
    return {"external_id": data.get("id", "")}


async def list_events(
    provider: str,
    access_token: str,
    time_min: datetime,
    time_max: datetime,
) -> list[dict[str, Any]]:
    """Devuelve eventos normalizados: {external_id, title, start_at, end_at}."""
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            if provider == "google":
                resp = await client.get(
                    GOOGLE_EVENTS_URL,
                    headers=headers,
                    params={
                        "timeMin": time_min.astimezone(UTC).isoformat(),
                        "timeMax": time_max.astimezone(UTC).isoformat(),
                        "singleEvents": "true",
                        "orderBy": "startTime",
                        "maxResults": 50,
                    },
                )
            else:
                resp = await client.get(
                    MS_CALENDARVIEW_URL,
                    headers={**headers, "Prefer": 'outlook.timezone="UTC"'},
                    params={
                        "startDateTime": time_min.astimezone(UTC).isoformat(),
                        "endDateTime": time_max.astimezone(UTC).isoformat(),
                        "$top": 50,
                    },
                )
    except httpx.HTTPError as exc:
        raise ExternalServiceError(f"{provider} no responde.") from exc
    if resp.status_code != 200:
        raise ExternalServiceError(f"No pude leer el calendario de {provider}.")
    items = resp.json().get("items" if provider == "google" else "value", [])
    events = []
    for it in items:
        if provider == "google":
            start = it.get("start", {}).get("dateTime") or it.get("start", {}).get("date")
            end = it.get("end", {}).get("dateTime") or it.get("end", {}).get("date")
            events.append(
                {
                    "external_id": it.get("id", ""),
                    "title": it.get("summary", "(sin título)"),
                    "start_at": _parse_dt(start),
                    "end_at": _parse_dt(end),
                }
            )
        else:
            events.append(
                {
                    "external_id": it.get("id", ""),
                    "title": it.get("subject", "(sin título)"),
                    "start_at": _parse_dt(it.get("start", {}).get("dateTime")),
                    "end_at": _parse_dt(it.get("end", {}).get("dateTime")),
                }
            )
    return [e for e in events if e["start_at"] is not None]


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        return None
