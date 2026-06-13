"""
bot/commands.py — Telegram bot command handlers.

Commands:
    /log [message]  — save a dev update to the database
    /status         — show the last 5 dev logs
    /generate       — generate a post from recent logs using AI
    /post_now       — post the latest generated post to the channel
    /news           — manually fetch news and post to the channel
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from config import Config
from storage import db
from engine import generator, fetcher
from poster.telegram import TelegramPoster

log = logging.getLogger(__name__)


def _is_admin(update: Update, cfg: Config) -> bool:
    """Return True if the message sender is the configured admin."""
    return update.effective_user.id == cfg.telegram_admin_id


async def cmd_log(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /log [message] — Save a dev update.

    Usage: /log finished the auth module, fixed rate limiting bug
    """
    cfg: Config = context.bot_data["cfg"]

    if not _is_admin(update, cfg):
        await update.message.reply_text("⛔ Unauthorised.")
        return

    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text("Usage: /log your update here")
        return

    row_id = db.save_log(cfg.db_path, text)
    log.info("Log saved by admin: id=%d", row_id)
    await update.message.reply_text(f"✅ Logged (#{row_id}): {text[:80]}")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /status — Show the last 5 dev logs.
    """
    cfg: Config = context.bot_data["cfg"]

    if not _is_admin(update, cfg):
        await update.message.reply_text("⛔ Unauthorised.")
        return

    logs = db.get_recent_logs(cfg.db_path, limit=5)
    if not logs:
        await update.message.reply_text("No logs yet. Use /log to add one.")
        return

    lines = ["📋 Last 5 logs:\n"]
    for entry in logs:
        date = entry["created_at"][:10]
        lines.append(f"[{date}] {entry['message'][:100]}")

    await update.message.reply_text("\n".join(lines))


async def cmd_generate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /generate — Generate a post from recent logs using AI.

    Optionally specify tone: /generate humorous
    Default tone: builder
    """
    cfg: Config = context.bot_data["cfg"]

    if not _is_admin(update, cfg):
        await update.message.reply_text("⛔ Unauthorised.")
        return

    tone = (context.args[0].lower() if context.args else "builder")
    if tone not in ("builder", "humorous", "technical"):
        await update.message.reply_text(
            "Invalid tone. Choose: builder, humorous, technical"
        )
        return

    logs = db.get_recent_logs(cfg.db_path, limit=10)
    if not logs:
        await update.message.reply_text("No logs found. Add some with /log first.")
        return

    await update.message.reply_text(f"⏳ Generating ({tone} tone)…")

    try:
        content, score = generator.generate_from_logs(
            logs=logs,
            tone=tone,
            groq_api_key=cfg.groq_api_key,
            groq_model=cfg.groq_model,
            groq_api_url=cfg.groq_api_url,
            gemini_api_key=cfg.gemini_api_key,
            gemini_model=cfg.gemini_model,
        )
    except generator.GeneratorError as exc:
        log.error("Generation failed: %s", exc)
        await update.message.reply_text(f"❌ Generation failed: {exc}")
        return

    post_id = db.save_post(cfg.db_path, content, tone=tone, source_type="log")
    log.info("Post generated: id=%d score=%d tone=%s", post_id, score, tone)

    await update.message.reply_text(
        f"✅ Post generated (score {score}/10, id #{post_id}):\n\n{content}"
    )


async def cmd_post_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /post_now — Post the latest generated post to the Telegram channel.
    """
    cfg: Config = context.bot_data["cfg"]

    if not _is_admin(update, cfg):
        await update.message.reply_text("⛔ Unauthorised.")
        return

    post = db.get_latest_post(cfg.db_path)
    if not post:
        await update.message.reply_text(
            "No posts available. Run /generate first."
        )
        return

    poster = TelegramPoster(cfg.telegram_bot_token, cfg.telegram_channel)
    success, msg_id, post_url = poster.post(post["content"])

    db.record_posting(
        cfg.db_path,
        post_id=post["id"],
        platform="telegram",
        success=success,
        message_id=msg_id,
        post_url=post_url,
        error=None if success else "post_now failed",
    )

    if success:
        link = f"\n🔗 {post_url}" if post_url else ""
        await update.message.reply_text(f"✅ Posted to channel!{link}")
    else:
        await update.message.reply_text("❌ Posting failed. Check logs.")


async def cmd_news(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /news — Manually fetch the top news article and post it to the channel.
    """
    cfg: Config = context.bot_data["cfg"]

    if not _is_admin(update, cfg):
        await update.message.reply_text("⛔ Unauthorised.")
        return

    await update.message.reply_text("⏳ Fetching news…")

    article = fetcher.fetch_best_article(cfg.rss_feeds)
    if not article:
        await update.message.reply_text("❌ No articles found from RSS feeds.")
        return

    try:
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
    except generator.GeneratorError as exc:
        log.error("News generation failed: %s", exc)
        await update.message.reply_text(f"❌ AI generation failed: {exc}")
        return

    if score < cfg.news_min_score:
        await update.message.reply_text(
            f"⚠️ Article scored {score}/10 (below threshold {cfg.news_min_score}). "
            "Not posting."
        )
        return

    post_id = db.save_post(cfg.db_path, content, tone="builder", source_type="news")

    poster = TelegramPoster(cfg.telegram_bot_token, cfg.telegram_channel)
    success, msg_id, post_url = poster.post(content)

    db.record_posting(
        cfg.db_path,
        post_id=post_id,
        platform="telegram",
        success=success,
        message_id=msg_id,
        post_url=post_url,
        error=None if success else "news command failed",
    )

    if success:
        link = f"\n🔗 {post_url}" if post_url else ""
        await update.message.reply_text(f"✅ News posted!{link}")
    else:
        await update.message.reply_text("❌ Posting failed. Content was saved.")
