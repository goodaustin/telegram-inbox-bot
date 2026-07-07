import asyncio
import logging
import sys
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot
from inbox_bot.bot import build_application
from inbox_bot.config import get_settings
from inbox_bot.digest import send_digest
from inbox_bot import reminders as rem


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


def register_digest_job(scheduler, settings) -> bool:
    if not settings.digest_enabled:
        logging.info("weekly digest disabled by config (DIGEST_ENABLED=false)")
        return False
    tz = ZoneInfo(settings.timezone)
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
    return True


def _parse_hhmm(s) -> tuple[int, int] | None:
    if not s or ":" not in str(s):
        return None
    h, _, m = str(s).partition(":")
    try:
        return int(h), int(m)
    except ValueError:
        return None


async def send_reminders(settings) -> None:
    """依 reminders.yaml 發本週剩餘額度提醒(每項一則),並記下 message_id→target。"""
    cfg = rem.load_reminders(settings.life_dir)
    if not cfg:
        return
    now = datetime.now(ZoneInfo(settings.timezone))
    msgs = rem.build_reminder_messages(cfg, settings.life_dir, now)
    if not msgs:
        logging.info("reminders: all targets met this week; staying silent")
        return
    bot = Bot(token=settings.telegram_bot_token)
    mapping: dict[str, str] = {}
    for target, text in msgs:
        m = await bot.send_message(chat_id=settings.telegram_channel_id, text=text)
        mapping[str(m.message_id)] = target["name"]
    rem.save_msgid_map(settings.life_dir, mapping)


def register_reminder_jobs(scheduler, settings) -> bool:
    """平日/假日各一個 cron job(時段由 reminders.yaml 的 check_times 決定)。"""
    if not settings.life_dir:
        return False
    cfg = rem.load_reminders(settings.life_dir)
    if not cfg:
        return False
    tz = ZoneInfo(settings.timezone)
    ct = cfg.get("check_times", {})
    added = False
    wd = _parse_hhmm(ct.get("weekday"))
    if wd:
        scheduler.add_job(
            send_reminders, CronTrigger(day_of_week="mon-fri", hour=wd[0], minute=wd[1], timezone=tz),
            kwargs={"settings": settings}, id="reminders_weekday", replace_existing=True,
        )
        added = True
    we = _parse_hhmm(ct.get("weekend"))
    if we:
        scheduler.add_job(
            send_reminders, CronTrigger(day_of_week="sat,sun", hour=we[0], minute=we[1], timezone=tz),
            kwargs={"settings": settings}, id="reminders_weekend", replace_existing=True,
        )
        added = True
    return added


async def _run() -> None:
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)

    app = build_application(settings)

    scheduler = AsyncIOScheduler(timezone=tz)
    register_digest_job(scheduler, settings)
    register_reminder_jobs(scheduler, settings)
    scheduler.start()  # start once; jobs may be zero (harmless, keeps shutdown symmetric)
    for jid in ("weekly_digest", "reminders_weekday", "reminders_weekend"):
        job = scheduler.get_job(jid)
        if job:
            logging.info("scheduled %s; next run: %s", jid, job.next_run_time)

    await app.initialize()
    await app.start()
    # Keep pending updates so messages posted while the bot was offline (e.g. the
    # laptop was asleep/closed) are processed on next start. Telegram retains
    # undelivered updates for ~24h; beyond that they are dropped server-side.
    await app.updater.start_polling(drop_pending_updates=False)
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
