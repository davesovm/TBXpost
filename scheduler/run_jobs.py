"""
scheduler/run_jobs.py — Stateless broadcast engine for GitHub Actions.

Runs twice a week (Mon + Thu). No database. No APScheduler.
Pipeline:
  1. Fetch top RSS article
  2. Curate with Groq/Gemini
  3. Post to Telegram
  4. Append result to broadcast_history.md and commit

Environment variables (set as GitHub Secrets):
  TELEGRAM_BOT_TOKEN  — bot token
  TELEGRAM_CHANNEL    — e.g. @sovm00
  GROQ_API_KEY        — Groq API key
  GROQ_MODEL          — optional, default llama-3.1-8b-instant
  GEMINI_API_KEY      — optional fallback
  NEWS_MIN_SCORE      — optional, default 7
  RSS_FEEDS           — comma-separated feed URLs
"""

import hashlib
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import feedparser

# ── Bootstrap logging ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# ── Add project root to path so core/ is importable ──────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))
from core import engine, telegram as tg

# ── Config from environment ───────────────────────────────────────────────────
TOKEN       = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHANNEL     = os.environ.get("TELEGRAM_CHANNEL", "").strip()
GROQ_KEY    = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_MODEL  = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_URL    = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_KEY  = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
MIN_SCORE   = int(os.environ.get("NEWS_MIN_SCORE", "7"))
RSS_FEEDS   = [
    f.strip() for f in
    os.environ.get(
        "RSS_FEEDS",
        "https://hnrss.org/frontpage,https://dev.to/feed"
    ).split(",")
    if f.strip()
]
HISTORY_FILE = Path(__file__).parent.parent / "broadcast_history.md"

# Noise / signal keywords for scoring
_NOISE = {"sponsored", "advertisement", "promoted", "giveaway"}
_SIGNAL = {"open source", "release", "performance", "security", "ai", "llm",
           "rust", "python", "kubernetes", "api", "benchmark", "architecture",
           "database", "typescript", "react", "tool", "library"}


def fetch_best_article() -> dict | None:
    """
    Fetch articles from all RSS feeds, deduplicate by URL,
    score by keyword relevance, and return the best one.
    Returns None if all feeds fail.
    """
    all_articles: list[dict] = []

    for feed_url in RSS_FEEDS:
        try:
            resp = requests.get(
                feed_url, timeout=15,
                headers={"User-Agent": "TBXpost-bot/1.0"},
            )
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)

            for entry in feed.entries[:20]:
                title = (getattr(entry, "title", "") or "").strip()
                url = (getattr(entry, "link", "") or "").strip()
                if not title or not url:
                    continue
                desc = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
                desc = re.sub(r"<[^>]+>", "", desc)
                desc = re.sub(r"\s+", " ", desc).strip()[:300]
                all_articles.append({"title": title, "desc": desc, "url": url})
            log.info("Feed %s → %d articles", feed_url, len(feed.entries))

        except Exception as exc:
            log.warning("Feed failed (%s): %s", feed_url, exc)

    if not all_articles:
        return None

    # Deduplicate by URL hash
    seen: set[str] = set()
    unique = []
    for a in all_articles:
        h = hashlib.md5(a["url"].encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            unique.append(a)

    # Score by keyword
    def score(a: dict) -> int:
        text = (a["title"] + " " + a["desc"]).lower()
        s = sum(1 for kw in _SIGNAL if kw in text)
        s -= sum(5 for kw in _NOISE if kw in text)
        return max(s, 0)

    best = max(unique, key=score)
    log.info("Best article (score=%d): %s", score(best), best["title"][:70])
    return best


def append_history(title: str, url: str, post_url: str | None, score: int) -> None:
    """
    Append one line to broadcast_history.md recording what was posted.
    Creates the file if it doesn't exist.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    line = f"| {now} | {title[:60]} | [source]({url}) | {post_url or 'n/a'} | {score}/10 |\n"

    if not HISTORY_FILE.exists():
        HISTORY_FILE.write_text(
            "# Broadcast History\n\n"
            "| Date | Title | Source | Telegram | AI Score |\n"
            "|------|-------|--------|----------|----------|\n"
        )

    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(line)

    log.info("History updated: %s", HISTORY_FILE)


def main() -> None:
    """
    Full broadcast pipeline. Exits 0 always —
    failures are logged but never crash the GitHub Action.
    """
    log.info("TBXpost broadcast starting")

    # Validate required secrets
    if not TOKEN or not CHANNEL:
        log.error("TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL are required.")
        sys.exit(1)

    if not GROQ_KEY and not GEMINI_KEY:
        log.error("At least one of GROQ_API_KEY or GEMINI_API_KEY is required.")
        sys.exit(1)

    # 1. Fetch best article
    article = fetch_best_article()
    if not article:
        log.warning("No articles found. Exiting.")
        sys.exit(0)

    # 2. Generate post with AI
    try:
        content, ai_score = engine.from_news(
            title=article["title"],
            desc=article["desc"],
            url=article["url"],
            tone="builder",
            groq_api_key=GROQ_KEY,
            groq_model=GROQ_MODEL,
            groq_api_url=GROQ_URL,
            gemini_api_key=GEMINI_KEY,
            gemini_model=GEMINI_MODEL,
        )
    except engine.GeneratorError as exc:
        log.error("AI generation failed: %s", exc)
        sys.exit(0)

    if ai_score < MIN_SCORE:
        log.info("Score %d below threshold %d — skipping post", ai_score, MIN_SCORE)
        sys.exit(0)

    log.info("Generated post (score=%d):\n%s", ai_score, content[:200])

    # 3. Post to Telegram
    success, msg_id, post_url = tg.send_message(TOKEN, CHANNEL, content)

    if not success:
        log.error("Telegram posting failed — history not updated")
        sys.exit(0)

    # 4. Append to broadcast_history.md
    append_history(article["title"], article["url"], post_url, ai_score)

    log.info("Broadcast complete. Post: %s", post_url or msg_id)


if __name__ == "__main__":
    main()
