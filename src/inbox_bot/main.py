import asyncio
import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from inbox_bot.bot import build_application
from inbox_bot.config import get_settings
from inbox_bot.digest import send_digest


def _setup_logging() -> None:
    logs_dir = Path(__file__).resolve().parents[2] / "logs"
    logs_dir.mkdir(exist_ok=True)
    handler = TimedRotatingFileHandler(
        logs_dir / "bot.log", when="midnight", backupCount=14, encoding="utf-8",
    )
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handler.setFormatter(fmt)
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    logging.basicConfig(level=logging.INFO, handlers=[handler, stream])
    # quiet noisy libs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.INFO)


async def _run() -> None:
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)

    app = build_application(settings)

    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.add_job(
        send_digest,
        trigger=CronTrigger(
            day_of_week="sun",
            hour=settings.digest_hour,
            minute=settings.digest_minute,
            timezone=tz,
        ),
        kwargs={"settings": settings},
        id="weekly_digest",
        replace_existing=True,
    )
    scheduler.start()
    logging.info("scheduler started; next digest: %s",
                 scheduler.get_job("weekly_digest").next_run_time)

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    logging.info("bot started (long-polling)")
    try:
        # block forever
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        scheduler.shutdown(wait=False)


def main() -> None:
    _setup_logging()
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logging.info("shutdown requested")


if __name__ == "__main__":
    main()
