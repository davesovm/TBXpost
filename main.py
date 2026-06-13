"""
main.py — Entry point for TBXpost.

Starts:
  1. SQLite database (auto-creates schema)
  2. APScheduler (registers 2x/week post jobs)
  3. Telegram bot (polling mode)

Run: python main.py
"""

import logging
import os
import sys

from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application

import config
from storage import db
from bot import handlers
from scheduler import jobs

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def main() -> None:
    """
    Bootstrap and run the bot.
    Exits with code 1 on misconfiguration.
    """
    # Load .env file if present (ignored in production where env vars are set)
    load_dotenv()

    # Load and validate configuration
    cfg = config.load()

    if not cfg.telegram_bot_token:
        log.error("TELEGRAM_BOT_TOKEN is required. Set it in your .env file.")
        sys.exit(1)

    if not cfg.telegram_channel:
        log.error("TELEGRAM_CHANNEL is required. Set it in your .env file.")
        sys.exit(1)

    if not cfg.telegram_admin_id:
        log.error("TELEGRAM_ADMIN_ID is required. Set it to your Telegram user ID.")
        sys.exit(1)

    # Initialise database
    db.init(cfg.db_path)
    log.info("Database ready: %s", cfg.db_path)

    # Build the Telegram application
    app = (
        Application.builder()
        .token(cfg.telegram_bot_token)
        .build()
    )

    # Share config with all command handlers via bot_data
    app.bot_data["cfg"] = cfg

    # Register command handlers
    handlers.register(app)

    # Set up APScheduler
    scheduler = AsyncIOScheduler()
    jobs.start(scheduler, cfg)

    # Start scheduler before polling
    scheduler.start()
    log.info("Scheduler started")

    log.info("TBXpost is running. Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)

    # Graceful shutdown
    scheduler.shutdown(wait=False)
    log.info("Shutdown complete.")


if __name__ == "__main__":
    main()
