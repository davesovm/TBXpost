"""
bot/handlers.py — Register all command and message handlers.

Import this module and call register() in main.py.
Add new commands here without touching any other file.
"""

import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from bot import commands

log = logging.getLogger(__name__)


def register(app: Application) -> None:
    """
    Register all bot handlers on the Application instance.

    Args:
        app: The python-telegram-bot Application.
    """
    app.add_handler(CommandHandler("log",      commands.cmd_log))
    app.add_handler(CommandHandler("status",   commands.cmd_status))
    app.add_handler(CommandHandler("generate", commands.cmd_generate))
    app.add_handler(CommandHandler("post_now", commands.cmd_post_now))
    app.add_handler(CommandHandler("news",     commands.cmd_news))

    # Catch-all: ignore non-command messages silently
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, _ignore)
    )

    log.info("Handlers registered: /log /status /generate /post_now /news")


async def _ignore(update, context) -> None:
    """Silently ignore plain text messages."""
