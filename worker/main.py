"""Worker arq: transcripción, OCR, indexado, sync de calendario y outbox."""

from arq import cron
from arq.connections import RedisSettings

from bot.dispatcher import create_bot
from core.config import get_settings
from core.database import dispose_engine
from core.logging import get_logger, setup_logging
from core.redis import close_redis
from gamification.engine import register as register_gamification
from worker.tasks.calendar_sync import calendar_sync
from worker.tasks.index_memory import index_memory, reindex_missing
from worker.tasks.ocr import process_document, process_image
from worker.tasks.outbox_flush import outbox_flush
from worker.tasks.transcribe import transcribe_voice

log = get_logger(__name__)


async def startup(ctx) -> None:
    s = get_settings()
    setup_logging(s.environment)
    if s.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(dsn=s.sentry_dsn, environment=s.environment)
    register_gamification()
    ctx["bot"] = create_bot()
    log.info("worker_started")


async def shutdown(ctx) -> None:
    bot = ctx.get("bot")
    if bot is not None:
        await bot.session.close()
    await close_redis()
    await dispose_engine()
    log.info("worker_stopped")


class WorkerSettings:
    functions = [
        transcribe_voice,
        process_image,
        process_document,
        index_memory,
        calendar_sync,
        outbox_flush,
        reindex_missing,
    ]
    cron_jobs = [
        cron(outbox_flush, minute=set(range(0, 60)), run_at_startup=False),
        cron(reindex_missing, minute={7, 27, 47}),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 10
    job_timeout = 120
