"""Parser de fechas naturales es-AR por timezone."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from core.errors import DateParseError
from domain.dates import parse_natural_datetime

TZ = "America/Argentina/Buenos_Aires"
# miércoles 10/06/2026 14:30 hora local
NOW = datetime(2026, 6, 10, 14, 30, tzinfo=ZoneInfo(TZ))


def parse(phrase: str):
    return parse_natural_datetime(phrase, TZ, now=NOW)


def test_manana_con_hora_am():
    dt = parse("mañana 9am")
    assert (dt.year, dt.month, dt.day, dt.hour, dt.minute) == (2026, 6, 11, 9, 0)


def test_manana_sin_hora_usa_9():
    dt = parse("mañana")
    assert (dt.day, dt.hour) == (11, 9)


def test_en_2_horas():
    dt = parse("en 2 horas")
    assert (dt.day, dt.hour, dt.minute) == (10, 16, 30)


def test_en_media_hora():
    dt = parse("en media hora")
    assert (dt.hour, dt.minute) == (15, 0)


def test_dia_semana_con_hora():
    dt = parse("el jueves 15hs")
    assert (dt.day, dt.hour) == (11, 15)  # jueves siguiente es 11/6


def test_dia_semana_que_viene():
    dt = parse("el miércoles que viene")
    assert dt.day == 17  # hoy es miércoles → el próximo


def test_hoy_a_la_tarde():
    dt = parse("hoy a la tarde")
    assert (dt.day, dt.hour) == (10, 16)


def test_hora_pm():
    dt = parse("hoy 8pm")
    assert (dt.day, dt.hour) == (10, 20)


def test_hora_pasada_se_corre_a_manana():
    dt = parse("a las 9")  # ya son 14:30
    assert (dt.day, dt.hour) == (11, 9)


def test_fecha_explicita():
    dt = parse("el 25/12 a las 10")
    assert (dt.month, dt.day, dt.hour) == (12, 25, 10)


def test_fecha_explicita_pasada_va_al_anio_proximo():
    dt = parse("el 3/1")
    assert (dt.year, dt.month, dt.day) == (2027, 1, 3)


def test_frase_invalida():
    with pytest.raises(DateParseError):
        parse("cuando las vacas vuelen")


def test_hora_con_minutos():
    dt = parse("mañana 15:45")
    assert (dt.hour, dt.minute) == (15, 45)


def test_timezone_distinta():
    dt = parse_natural_datetime("mañana 9am", "Europe/Madrid", now=NOW)
    assert dt.tzinfo is not None
    assert dt.utcoffset().total_seconds() == 2 * 3600  # CEST en junio
