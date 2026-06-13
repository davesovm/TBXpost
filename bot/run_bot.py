"""
bot/run_bot.py — Local daemon entry point.

Runs on your machine as a systemd service.
Handles all interactive commands: /log /status /generate /post_now /news
All data stays local in SQLite.

Run directly:
    python bot/run_bot.py

Or via systemd (see tbxpost.service).
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telegram.ext import Application

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot import handlers
from storage import db
import config

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def main() -> None:
    """Bootstrap and run the interactive bot locally."""
    # Load .env from project root
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)

    cfg = config.load()

    if not cfg.telegram_bot_token:
        log.error("TELEGRAM_BOT_TOKEN is required.")
        sys.exit(1)
    if not cfg.telegram_admin_id:
        log.error("TELEGRAM_ADMIN_ID is required. Get yours from @userinfobot.")
        sys.exit(1)

    # Initialise local SQLite database
    db.init(cfg.db_path)
    log.info("Database ready: %s", cfg.db_path)

    # Build and configure the Telegram application
    app = Application.builder().token(cfg.telegram_bot_token).build()
    app.bot_data["cfg"] = cfg

    # Register all command handlers
    handlers.register(app)

    log.info("TBXpost local bot running. Send /status to test.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
