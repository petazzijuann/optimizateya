"""Fixtures: DB SQLite async, Redis fake, LLM/STT mockeados, event bus limpio.

Las env vars se setean ANTES de importar core.config (validación al boot).
"""

import os

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TEST-token")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("PUBLIC_BASE_URL", "https://test.example.com")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://test:test@localhost:9/test"
)  # nunca se conecta: el engine se reemplaza abajo
os.environ.setdefault("REDIS_URL", "redis://localhost:9/0")
os.environ.setdefault("FERNET_KEY", "8Fb0Hn9d4-jBdrYOIs2BzXTC8w9DBOJusLLfuM9I9PU=")
os.environ.setdefault("GROQ_API_KEY", "test-key")

import json
from types import SimpleNamespace

import fakeredis.aioredis
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import core.database as core_db
from core.events import get_event_bus
from core.models import Base, User
from core.redis import set_redis


@pytest.fixture
async def redis():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    set_redis(client)
    yield client
    await client.flushall()
    set_redis(None)  # type: ignore[arg-type]


@pytest.fixture
async def db_engine():
    from sqlalchemy import event

    engine = create_async_engine("sqlite+aiosqlite://")

    @event.listens_for(engine.sync_engine, "connect")
    def _fk_on(dbapi_conn, _record):  # SQLite: honrar ON DELETE CASCADE como Postgres
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # session_scope() de todo el código usa estos globals
    core_db._engine = engine
    core_db._session_factory = async_sessionmaker(engine, expire_on_commit=False)
    yield engine
    core_db._engine = None
    core_db._session_factory = None
    await engine.dispose()


@pytest.fixture
async def session(db_engine):
    async with core_db.get_session_factory()() as s:
        yield s
        await s.commit()


@pytest.fixture
async def user(session) -> User:
    u = User(
        telegram_id=111222333,
        username="testuser",
        first_name="Test",
        timezone="America/Argentina/Buenos_Aires",
        onboarded=True,
    )
    session.add(u)
    await session.flush()
    await session.commit()
    return u


@pytest.fixture(autouse=True)
def clean_event_bus():
    bus = get_event_bus()
    bus.clear()
    yield
    bus.clear()


# ---------- mocks de IA ----------


def make_tool_call(name: str, arguments: dict) -> SimpleNamespace:
    return SimpleNamespace(
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
        id="call_test",
    )


class FakeLLMClient:
    """Devuelve respuestas predefinidas; registra los mensajes recibidos."""

    def __init__(self, tool_calls=None, content=None):
        self.tool_calls = tool_calls
        self.content = content
        self.calls: list[dict] = []

    async def chat(self, messages, tools=None, **kwargs):
        self.calls.append({"messages": messages, "tools": tools})
        return SimpleNamespace(tool_calls=self.tool_calls, content=self.content)


class FailingEmbeddings:
    """Fuerza el fallback a búsqueda por texto."""

    class embeddings:  # noqa: N801
        @staticmethod
        async def create(**kwargs):
            raise ConnectionError("ollama down")


@pytest.fixture
def no_embeddings():
    from ai.embeddings import set_embeddings_client

    set_embeddings_client(FailingEmbeddings())
    yield
    set_embeddings_client(None)


@pytest.fixture
def llm(request):
    """Inyecta un FakeLLMClient; configurable con make_tool_call."""
    from ai.client import set_llm_client

    client = FakeLLMClient()
    set_llm_client(client)  # type: ignore[arg-type]
    yield client
    set_llm_client(None)
