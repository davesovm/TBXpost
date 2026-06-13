"""
main.py — Render entry point for TBXpost.

On Render this runs as a Worker service.
Starts the Telegram bot (polling) + APScheduler for 2x/day broadcasts.

Schedule: 06:00 UTC and 18:00 UTC every day.
Interactive commands (/log /status /generate /post_now /news) work live.
Broadcasts use the same core/ engine — no GitHub Actions needed when on Render.

Run locally:  python main.py
Render:       python main.py  (set via render.yaml startCommand)
"""

import logging
import sys

from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram.ext import Application

import config
from storage import db
from bot import handlers
from core import engine, telegram as tg
from engine.fetcher import fetch_best_article

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


async def broadcast_job(cfg: config.Config) -> None:
    """
    Scheduled broadcast: fetch top news, generate post, publish to channel.
    Runs at 06:00 and 18:00 UTC daily.
    Stateless — does not read or write to the local database.
    """
    log.info("Broadcast job starting")

    article = fetch_best_article(cfg.rss_feeds)
    if not article:
        log.warning("Broadcast: no articles found")
        return

    try:
        content, score = engine.from_news(
            title=article["title"],
            desc=article["desc"],
            url=article["url"],
            tone="builder",
            groq_api_key=cfg.groq_api_key,
            groq_model=cfg.groq_model,
            groq_api_url=cfg.groq_api_url,
            gemini_api_key=cfg.gemini_api_key,
            gemini_model=cfg.gemini_model,
        )
    except engine.GeneratorError as exc:
        log.error("Broadcast: AI generation failed: %s", exc)
        return

    if score < cfg.news_min_score:
        log.info("Broadcast: score %d below threshold %d — skipping", score, cfg.news_min_score)
        return

    success, msg_id, post_url = tg.send_message(
        cfg.telegram_bot_token, cfg.telegram_channel, content
    )
    if success:
        log.info("Broadcast complete: %s", post_url or msg_id)
    else:
        log.error("Broadcast: Telegram posting failed")


def main() -> None:
    """Bootstrap and run the bot + scheduler on Render."""
    load_dotenv()
    cfg = config.load()

    if not cfg.telegram_bot_token:
        log.error("TELEGRAM_BOT_TOKEN is required.")
        sys.exit(1)
    if not cfg.telegram_channel:
        log.error("TELEGRAM_CHANNEL is required.")
        sys.exit(1)
    if not cfg.telegram_admin_id:
        log.error("TELEGRAM_ADMIN_ID is required.")
        sys.exit(1)

    # Database for interactive commands
    db.init(cfg.db_path)
    log.info("Database ready: %s", cfg.db_path)

    # Telegram bot application
    app = Application.builder().token(cfg.telegram_bot_token).build()
    app.bot_data["cfg"] = cfg
    handlers.register(app)

    # APScheduler — 2x/day broadcasts
    scheduler = AsyncIOScheduler(timezone=cfg.timezone)
    scheduler.add_job(
        broadcast_job,
        trigger=CronTrigger(hour=6, minute=0, timezone=cfg.timezone),
        kwargs={"cfg": cfg},
        id="broadcast_morning",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        broadcast_job,
        trigger=CronTrigger(hour=18, minute=0, timezone=cfg.timezone),
        kwargs={"cfg": cfg},
        id="broadcast_evening",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    log.info("Scheduler ready: broadcasts at 06:00 and 18:00 %s", cfg.timezone)

    log.info("TBXpost is running.")
    app.run_polling(drop_pending_updates=True)

    scheduler.shutdown(wait=False)
    log.info("Shutdown complete.")


if __name__ == "__main__":
    main()
