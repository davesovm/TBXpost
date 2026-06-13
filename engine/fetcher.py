"""
engine/fetcher.py — RSS fetch and article filtering.

Fetches from multiple RSS feeds, deduplicates, and returns
the highest-quality article based on a simple scoring heuristic.
"""

import hashlib
import logging
import time
from typing import Optional

import feedparser
import requests

log = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# Keywords that indicate low-value content
NOISE_KEYWORDS = {
    "sponsored", "advertisement", "partner content",
    "promoted", "giveaway", "win a", "prize",
}

# Keywords that boost score (relevant to developers)
SIGNAL_KEYWORDS = {
    "open source", "release", "performance", "security",
    "ai", "llm", "rust", "python", "kubernetes", "api",
    "benchmark", "architecture", "database", "postgres",
    "typescript", "react", "tool", "library",
}


def fetch_best_article(rss_feeds: list[str]) -> Optional[dict]:
    """
    Fetch articles from all configured RSS feeds.
    Returns the highest-scoring article or None if all feeds fail.

    Article dict keys:
        title, desc, url, published, source, score
    """
    all_articles: list[dict] = []

    for feed_url in rss_feeds:
        articles = _fetch_feed(feed_url.strip())
        all_articles.extend(articles)
        log.debug("Feed %s → %d articles", feed_url, len(articles))

    if not all_articles:
        log.warning("No articles fetched from any feed")
        return None

    # Deduplicate by URL hash
    seen: set[str] = set()
    unique: list[dict] = []
    for article in all_articles:
        h = hashlib.md5(article["url"].encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            unique.append(article)

    # Score and sort
    scored = [_score_article(a) for a in unique]
    scored.sort(key=lambda a: a["score"], reverse=True)

    best = scored[0]
    log.info(
        "Best article (score=%d): %s", best["score"], best["title"][:70]
    )
    return best


# ── Internal ──────────────────────────────────────────────────────────────────

def _fetch_feed(feed_url: str) -> list[dict]:
    """
    Fetch and parse a single RSS feed with retry logic.
    Returns a list of article dicts. Returns [] on failure.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # feedparser handles its own HTTP but we use requests for timeout control
            resp = requests.get(
                feed_url,
                timeout=15,
                headers={"User-Agent": "TBXpost-bot/1.0"},
            )
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)

            articles = []
            for entry in feed.entries[:20]:
                article = _normalise_entry(entry, feed_url)
                if article:
                    articles.append(article)
            return articles

        except Exception as exc:
            log.warning(
                "Feed fetch attempt %d/%d failed (%s): %s",
                attempt, MAX_RETRIES, feed_url, exc,
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    return []


def _normalise_entry(entry: feedparser.FeedParserDict, source: str) -> Optional[dict]:
    """
    Normalise a feedparser entry into a consistent article dict.
    Returns None if the entry is missing required fields.
    """
    title = (getattr(entry, "title", "") or "").strip()
    url = (getattr(entry, "link", "") or "").strip()

    if not title or not url:
        return None

    desc = (
        getattr(entry, "summary", "")
        or getattr(entry, "description", "")
        or ""
    )
    # Strip HTML tags
    import re
    desc = re.sub(r"<[^>]+>", "", desc)
    desc = re.sub(r"\s+", " ", desc).strip()[:300]

    published = ""
    if hasattr(entry, "published"):
        published = str(entry.published)[:10]

    return {
        "title": title,
        "desc": desc,
        "url": url,
        "published": published,
        "source": source,
        "score": 0,
    }


def _score_article(article: dict) -> dict:
    """
    Score an article based on title/desc keyword relevance.
    Modifies and returns the article dict with 'score' set.
    """
    text = (article["title"] + " " + article["desc"]).lower()
    score = 0

    # Penalise noise
    for kw in NOISE_KEYWORDS:
        if kw in text:
            score -= 5

    # Reward signal
    for kw in SIGNAL_KEYWORDS:
        if kw in text:
            score += 1

    # Reward longer descriptions (more context = more useful)
    if len(article["desc"]) > 100:
        score += 1

    article["score"] = max(score, 0)
    return article
