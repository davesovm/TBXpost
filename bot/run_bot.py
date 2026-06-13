"""
bot/run_bot.py — Local daemon entry point.

Runs on your Linux machine as a systemd service (see tbxpost.service).
Handles all interactive commands: /log /status /generate /post_now /news
All data stays local in SQLite — nothing leaves your machine until
you explicitly run /post_now.

Run manually:
    cd ~/Desktop/sovm's/TBXpost
    source venv/bin/activate
    python bot/run_bot.py

Or as a background service (see tbxpost.service).
"""

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
from telegram.ext import Application

# Add project root to path so all imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot import handlers
from storage import db
import config

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
        log.error("TELEGRAM_BOT_TOKEN is required. Fill it in .env")
        sys.exit(1)
    if not cfg.telegram_admin_id:
        log.error("TELEGRAM_ADMIN_ID is required. Get yours from @userinfobot")
        sys.exit(1)

    # Initialise local SQLite database (auto-creates schema)
    db.init(cfg.db_path)
    log.info("Database ready: %s", cfg.db_path)

    # Build the Telegram application with extended timeouts for slow networks
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(connect_timeout=30, read_timeout=30, write_timeout=30)
    app = Application.builder().token(cfg.telegram_bot_token).request(request).build()
    app.bot_data["cfg"] = cfg

    # Register all command handlers
    handlers.register(app)

    log.info("TBXpost local bot running.")
    log.info("Send /status to your bot on Telegram to confirm it works.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
