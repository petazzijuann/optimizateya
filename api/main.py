"""App FastAPI: webhook de Telegram, OAuth de calendarios, health y métricas."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from api.routers import health, oauth, telegram
from bot.dispatcher import create_bot, create_dispatcher
from core.config import get_settings
from core.database import dispose_engine, session_scope
from core.logging import get_logger, setup_logging
from core.redis import close_redis
from gamification.engine import register as register_gamification
from gamification.engine import seed_achievements

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    setup_logging(s.environment)
    if s.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(dsn=s.sentry_dsn, environment=s.environment)

    register_gamification()
    try:
        async with session_scope() as session:
            await seed_achievements(session)
    except Exception:
        log.warning("achievement_seed_skipped")  # DB aún no migrada, etc.

    app.state.bot = create_bot()
    app.state.dispatcher = create_dispatcher()
    log.info("api_started", env=s.environment)
    yield
    await app.state.bot.session.close()
    await close_redis()
    await dispose_engine()


app = FastAPI(title="Optimizate Ya", version="0.1.0", lifespan=lifespan, docs_url=None)

app.include_router(health.router)
app.include_router(telegram.router)
app.include_router(oauth.router)


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest().decode(), media_type=CONTENT_TYPE_LATEST)
