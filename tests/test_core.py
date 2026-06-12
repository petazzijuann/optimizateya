"""Tests de core: crypto (round-trip Fernet), event bus, config."""

import pytest

from core.crypto import decrypt_token, encrypt_token
from core.events import WILDCARD, DomainEvent, EventBus


def test_fernet_round_trip():
    secret = "ya29.a0AfH6SMC-token-super-secreto"
    encrypted = encrypt_token(secret)
    assert encrypted != secret.encode()
    assert decrypt_token(encrypted) == secret


def test_fernet_unicode():
    assert decrypt_token(encrypt_token("contraseña-ñandú-🔐")) == "contraseña-ñandú-🔐"


async def test_event_bus_publish_subscribe():
    bus = EventBus()
    received = []

    async def handler(event):
        received.append(event.type)

    bus.subscribe("reminder.created", handler)
    await bus.publish(DomainEvent(type="reminder.created", user_id="u1"))
    await bus.publish(DomainEvent(type="other.event", user_id="u1"))
    assert received == ["reminder.created"]


async def test_event_bus_wildcard_and_failure_isolation():
    bus = EventBus()
    received = []

    async def broken(event):
        raise RuntimeError("boom")

    async def ok(event):
        received.append(event.type)

    bus.subscribe(WILDCARD, broken)
    bus.subscribe(WILDCARD, ok)
    await bus.publish(DomainEvent(type="x", user_id="u1"))
    assert received == ["x"]  # el handler roto no rompe a los demás


def test_config_normalizes_supabase_style_url(monkeypatch):
    from core.config import Settings

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://postgres.abc:pw@aws-0-sa-east-1.pooler.supabase.com:5432/postgres?sslmode=require",
    )
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.database_url.startswith("postgresql+asyncpg://")
    assert "ssl=require" in s.database_url
    assert "sslmode" not in s.database_url
    # y la variante sync vuelve al formato libpq
    assert "sslmode=require" in s.database_url_sync


def test_config_normalizes_heroku_style_scheme(monkeypatch):
    from core.config import Settings

    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@host:5432/db")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.database_url == "postgresql+asyncpg://user:pass@host:5432/db"


def test_config_rejects_non_postgres(monkeypatch):
    from pydantic import ValidationError as PydanticValidationError

    from core.config import Settings

    monkeypatch.setenv("DATABASE_URL", "mysql://user:pass@localhost/db")
    with pytest.raises(PydanticValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_config_database_url_sync_property():
    from core.config import get_settings

    s = get_settings()
    assert s.database_url_sync.startswith("postgresql+psycopg2://")
