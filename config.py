"""
config.py — Load and validate all environment variables.

All configuration lives here. Nothing else reads os.environ directly.
"""

import os
import logging
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


@dataclass
class Config:
    """All runtime configuration, loaded from environment variables."""

    # ── Telegram ──────────────────────────────────────────────────────────────
    telegram_bot_token: str = ""
    telegram_channel: str = ""
    telegram_admin_id: int = 0

    # ── AI — Groq (primary) ───────────────────────────────────────────────────
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"
    groq_api_url: str = "https://api.groq.com/openai/v1/chat/completions"

    # ── AI — Gemini (fallback) ────────────────────────────────────────────────
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"

    # ── Scheduler ─────────────────────────────────────────────────────────────
    post_days: list = field(default_factory=lambda: ["mon", "thu"])
    post_hour: int = 9
    post_minute: int = 0
    timezone: str = "UTC"

    # ── Storage ───────────────────────────────────────────────────────────────
    db_path: str = "tbxpost.db"

    # ── News ──────────────────────────────────────────────────────────────────
    rss_feeds: list = field(default_factory=lambda: [
        "https://hnrss.org/frontpage",
        "https://dev.to/feed",
        "https://feeds.feedburner.com/ThePythonPodcast",
    ])
    news_min_score: int = 7


def load() -> Config:
    """
    Load configuration from environment variables.
    Logs a warning for each missing required variable.
    Returns a Config instance (never raises).
    """
    cfg = Config(
        telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        telegram_channel=os.environ.get("TELEGRAM_CHANNEL", ""),
        telegram_admin_id=int(os.environ.get("TELEGRAM_ADMIN_ID", "0")),
        groq_api_key=os.environ.get("GROQ_API_KEY", ""),
        groq_model=os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant"),
        gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
        gemini_model=os.environ.get("GEMINI_MODEL", "gemini-1.5-flash"),
        post_days=os.environ.get("POST_DAYS", "mon,thu").lower().split(","),
        post_hour=int(os.environ.get("POST_HOUR", "9")),
        post_minute=int(os.environ.get("POST_MINUTE", "0")),
        timezone=os.environ.get("TIMEZONE", "UTC"),
        db_path=os.environ.get("DB_PATH", "tbxpost.db"),
        rss_feeds=os.environ.get(
            "RSS_FEEDS",
            "https://hnrss.org/frontpage,https://dev.to/feed",
        ).split(","),
        news_min_score=int(os.environ.get("NEWS_MIN_SCORE", "7")),
    )

    _warn_if_missing(cfg)
    return cfg


def _warn_if_missing(cfg: Config) -> None:
    """Log warnings for any missing required fields."""
    required = {
        "TELEGRAM_BOT_TOKEN": cfg.telegram_bot_token,
        "TELEGRAM_CHANNEL": cfg.telegram_channel,
        "TELEGRAM_ADMIN_ID": cfg.telegram_admin_id,
        "GROQ_API_KEY": cfg.groq_api_key,
    }
    for name, value in required.items():
        if not value:
            log.warning("Missing required env var: %s", name)
