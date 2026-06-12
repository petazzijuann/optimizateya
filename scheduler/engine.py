"""Proceso scheduler: APScheduler (asyncio) con los jobs temporizados del sistema.

Los recordatorios NO se programan como jobs individuales: la DB es la fuente
de verdad y `fire_due` la consulta cada 30 s (precisión ±1 min del RNF, sin
coordinación de jobstores entre procesos).
"""

import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from bot.dispatcher import create_bot
from core.config import get_settings
from core.database import dispose_engine
from core.logging import get_logger, setup_logging
from core.redis import close_redis
from gamification.engine import register as register_gamification
from scheduler.jobs.calendar_reconcile import reconcile_all
from scheduler.jobs.daily_briefing import send_briefings
from scheduler.jobs.leaderboard_snapshot import snapshot
from scheduler.jobs.reminder_fire import fire_due
from scheduler.jobs.retention_gc import run_gc

log = get_logger(__name__)


def build_scheduler(bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        fire_due, IntervalTrigger(seconds=30), args=[bot], id="fire_due", max_instances=1
    )
    scheduler.add_job(
        send_briefings,
        IntervalTrigger(minutes=10),
        args=[bot],
        id="daily_briefing",
        max_instances=1,
    )
    scheduler.add_job(snapshot, IntervalTrigger(minutes=15), id="leaderboard_snapshot")
    scheduler.add_job(reconcile_all, IntervalTrigger(minutes=30), id="calendar_reconcile")
    scheduler.add_job(run_gc, CronTrigger(hour=4, minute=0), id="retention_gc")
    return scheduler


async def main() -> None:
    s = get_settings()
    setup_logging(s.environment)
    if s.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(dsn=s.sentry_dsn, environment=s.environment)
    register_gamification()
    bot = create_bot()
    scheduler = build_scheduler(bot)
    scheduler.start()
    log.info("scheduler_started")
    try:
        await asyncio.Event().wait()  # corre para siempre
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await close_redis()
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
