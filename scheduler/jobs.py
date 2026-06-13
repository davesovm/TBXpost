"""
scheduler/jobs.py — APScheduler jobs for automated posting.

Schedule: 2x/week (configurable via POST_DAYS env var).
Alternates between dev-log posts and news posts each run.
Retry: 3 attempts with 5-minute backoff on failure.
"""

import logging
import time
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import Config
from storage import db
from engine import generator, fetcher
from poster.telegram import TelegramPoster

log = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 300  # 5 minutes in seconds

# Tracks which post type runs next: True = log post, False = news post
_post_log_next: bool = True


def start(scheduler: AsyncIOScheduler, cfg: Config) -> None:
    """
    Register all scheduled jobs on the given scheduler.
    The scheduler must be started externally (done in main.py).

    Args:
        scheduler: An APScheduler AsyncIOScheduler instance.
        cfg: Loaded configuration.
    """
    day_map = {
        "mon": "mon", "tue": "tue", "wed": "wed",
        "thu": "thu", "fri": "fri", "sat": "sat", "sun": "sun",
    }
    days = ",".join(day_map.get(d.strip(), "mon") for d in cfg.post_days)

    trigger = CronTrigger(
        day_of_week=days,
        hour=cfg.post_hour,
        minute=cfg.post_minute,
        timezone=cfg.timezone,
    )

    scheduler.add_job(
        _scheduled_post,
        trigger=trigger,
        kwargs={"cfg": cfg},
        id="scheduled_post",
        replace_existing=True,
        misfire_grace_time=3600,  # allow up to 1h late start
    )

    log.info(
        "Scheduled post job: days=%s at %02d:%02d %s",
        days, cfg.post_hour, cfg.post_minute, cfg.timezone,
    )


async def _scheduled_post(cfg: Config) -> None:
    """
    Execute a scheduled post. Alternates between log and news posts.
    Retries up to MAX_RETRIES times on failure.
    """
    global _post_log_next

    post_type = "log" if _post_log_next else "news"
    log.info("Scheduled post triggered: type=%s", post_type)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if post_type == "log":
                success = await _run_log_post(cfg)
            else:
                success = await _run_news_post(cfg)

            if success:
                # Flip for next run
                _post_log_next = not _post_log_next
                log.info("Scheduled post completed: type=%s", post_type)
                return

        except Exception as exc:
            log.error(
                "Scheduled post attempt %d/%d failed: %s",
                attempt, MAX_RETRIES, exc,
            )

        if attempt < MAX_RETRIES:
            log.info("Retrying in %d seconds…", RETRY_DELAY)
            time.sleep(RETRY_DELAY)

    log.error("Scheduled post failed after %d attempts — skipping", MAX_RETRIES)


async def _run_log_post(cfg: Config) -> bool:
    """
    Generate a post from recent logs and publish it.
    Returns True on success.
    """
    logs = db.get_recent_logs(cfg.db_path, limit=10)
    if not logs:
        log.warning("No logs found for scheduled post — skipping")
        return False

    content, score = generator.generate_from_logs(
        logs=logs,
        tone="builder",
        groq_api_key=cfg.groq_api_key,
        groq_model=cfg.groq_model,
        groq_api_url=cfg.groq_api_url,
        gemini_api_key=cfg.gemini_api_key,
        gemini_model=cfg.gemini_model,
    )

    post_id = db.save_post(cfg.db_path, content, tone="builder", source_type="log")
    return _publish(cfg, content, post_id)


async def _run_news_post(cfg: Config) -> bool:
    """
    Fetch top news, generate a post, and publish it.
    Returns True on success.
    """
    article = fetcher.fetch_best_article(cfg.rss_feeds)
    if not article:
        log.warning("No news article found for scheduled post — skipping")
        return False

    content, score = generator.generate_from_news(
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

    if score < cfg.news_min_score:
        log.info("Article score %d below threshold — skipping post", score)
        return False

    post_id = db.save_post(cfg.db_path, content, tone="builder", source_type="news")
    return _publish(cfg, content, post_id)


def _publish(cfg: Config, content: str, post_id: int) -> bool:
    """Post content to Telegram and record the result. Returns success bool."""
    poster = TelegramPoster(cfg.telegram_bot_token, cfg.telegram_channel)
    success, msg_id, post_url = poster.post(content)

    db.record_posting(
        cfg.db_path,
        post_id=post_id,
        platform="telegram",
        success=success,
        message_id=msg_id,
        post_url=post_url,
        error=None if success else "scheduled post failed",
    )
    return success
