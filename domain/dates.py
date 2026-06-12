"""Parsing de fechas/horas relativas en español rioplatense, por timezone del usuario.

Determinístico (sin LLM): el NLU pasa la frase tal cual ("mañana 9am") y acá
se resuelve contra el reloj local del usuario.
"""

import re
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from core.errors import DateParseError

_WEEKDAYS = {
    "lunes": 0,
    "martes": 1,
    "miercoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sabado": 5,
    "domingo": 6,
}

_UNITS_MIN = {"minuto": 1, "min": 1, "hora": 60, "dia": 60 * 24, "semana": 60 * 24 * 7}

_DAYPART_HOURS = {
    "madrugada": 6,
    "manana": 9,
    "mediodia": 12,
    "tarde": 16,
    "noche": 21,
}

_NUM_WORDS = {
    "una": 1, "un": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11,
    "doce": 12, "quince": 15, "veinte": 20, "treinta": 30, "media": 30,
}


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", text).strip()


def _parse_time(text: str) -> tuple[int, int] | None:
    """Devuelve (hora, minuto) si hay hora explícita en el texto."""
    # 15:30 / 9.30
    m = re.search(r"\b(\d{1,2})[:.](\d{2})\b", text)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if h < 24 and mi < 60:
            if h < 12 and ("tarde" in text or "noche" in text or "pm" in text):
                h += 12
            return h, mi
    # 9am / 9 pm / 15hs / 15 hs / a las 9
    m = re.search(r"\b(\d{1,2})\s*(am|pm|hs|h\b|horas)", text)
    if not m:
        m = re.search(r"a las (\d{1,2})\b", text)
    if m:
        h = int(m.group(1))
        suffix = m.group(2) if m.lastindex and m.lastindex >= 2 else ""
        if suffix == "pm" and h < 12:
            h += 12
        elif suffix != "am" and h < 12 and ("tarde" in text or "noche" in text):
            h += 12
        if h < 24:
            return h, 0
    # "a la tarde", "de la manana", "al mediodia"
    for part, hour in _DAYPART_HOURS.items():
        if re.search(rf"\b(a la|a el|al|de la|por la) {part}\b", text) or text == part:
            return hour, 0
    return None


def parse_natural_datetime(
    phrase: str, timezone: str, now: datetime | None = None
) -> datetime:
    """Resuelve una frase tipo 'mañana 9am' a un datetime aware en la tz del usuario.

    Lanza DateParseError si no se puede interpretar.
    """
    tz = ZoneInfo(timezone)
    now = (now or datetime.now(tz)).astimezone(tz)
    text = _normalize(phrase)
    if not text:
        raise DateParseError("No entendí la fecha. ¿Me decís cuándo? (ej: 'mañana 9am')")

    # --- relativo: "en 2 horas", "en media hora", "en 15 minutos" ---
    m = re.search(r"\ben (\d+|\w+) (minutos?|min|horas?|dias?|semanas?)\b", text)
    if m:
        qty_raw = m.group(1)
        qty = int(qty_raw) if qty_raw.isdigit() else _NUM_WORDS.get(qty_raw, 0)
        unit = m.group(2).rstrip("s")
        if qty and unit in _UNITS_MIN:
            if qty_raw == "media" and unit == "hora":
                return now + timedelta(minutes=30)
            return now + timedelta(minutes=qty * _UNITS_MIN[unit])

    base_date = None
    if "pasado manana" in text:
        base_date = (now + timedelta(days=2)).date()
    elif "manana" in text and not re.search(r"(a la|de la|por la) manana", text):
        base_date = (now + timedelta(days=1)).date()
    elif "hoy" in text or "esta noche" in text or "esta tarde" in text:
        base_date = now.date()

    # --- día de la semana: "el jueves", "jueves que viene" ---
    if base_date is None:
        for day_name, day_num in _WEEKDAYS.items():
            if re.search(rf"\b{day_name}\b", text):
                delta = (day_num - now.weekday()) % 7
                if delta == 0:
                    delta = 7 if "que viene" in text or "proximo" in text else 0
                candidate = (now + timedelta(days=delta)).date()
                base_date = candidate
                break

    # --- fecha explícita: 25/12 o 25/12/2026 ---
    if base_date is None:
        m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", text)
        if m:
            day, month = int(m.group(1)), int(m.group(2))
            year = int(m.group(3)) if m.group(3) else now.year
            if year < 100:
                year += 2000
            try:
                base_date = datetime(year, month, day).date()
                if not m.group(3) and base_date < now.date():
                    base_date = datetime(year + 1, month, day).date()
            except ValueError as exc:
                raise DateParseError(f"'{phrase}' no parece una fecha válida.") from exc

    time_part = _parse_time(text)

    if base_date is None and time_part is None:
        raise DateParseError(
            f"No pude interpretar '{phrase}'. Probá con algo como 'mañana 9am' o 'el jueves 15hs'."
        )

    if base_date is None:
        base_date = now.date()
    hour, minute = time_part if time_part else (9, 0)

    result = datetime(base_date.year, base_date.month, base_date.day, hour, minute, tzinfo=tz)

    # si quedó en el pasado y no se nombró día explícito, pasa al día siguiente
    if result <= now:
        if time_part and base_date == now.date():
            result += timedelta(days=1)
        else:
            raise DateParseError(f"'{phrase}' quedó en el pasado. ¿Me das una fecha futura?")
    return result
