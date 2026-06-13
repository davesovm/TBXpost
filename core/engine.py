"""
core/engine.py — Shared AI generation logic.

Used by both bot/ (interactive) and scheduler/ (broadcast).
Primary: Groq. Fallback: Gemini. Stateless — no database dependency.
"""

import logging
import re
import time
from typing import Optional

import requests

log = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# ── Prompt templates ──────────────────────────────────────────────────────────

_POST_FORMAT = """
Post structure (follow exactly):
HOOK — one punchy sentence, alone on its own line

SETUP — 1-2 sentences of context

INSIGHT — one sharp observation

TAKE — what this means for builders (1 sentence)

👇 One discussion question

🔗 Source: [URL or "Personal log"]

Max 90 words. No bullets. No headers. No numbered lists.
Never use: game-changer, revolutionary, paradigm shift, future of,
exciting, amazing, incredible, leverage, utilize, delve.
"""

SYSTEM_PROMPTS = {
    "builder": f"""
You are a solo builder who ships AI products and automation tools.
You are a signal filter, not a journalist.
Voice: short, direct, human, slightly opinionated, no hype.
Think: "Interesting. Here's what I noticed."
{_POST_FORMAT}
Respond EXACTLY as:
SCORE: <0-10>
---POST---
<post content>
---END---
""",
    "humorous": f"""
You are a developer with dry wit who has seen too many frameworks come and go.
Voice: self-aware, never mean-spirited, never forced.
Think: a senior dev tweeting at 2am who actually ships.
{_POST_FORMAT}
Respond EXACTLY as:
SCORE: <0-10>
---POST---
<post content>
---END---
""",
    "technical": f"""
You are a staff engineer explaining a concept to a sharp junior.
Voice: precise, concrete, skips fluff, uses real terms.
Think: a code review comment that makes someone better.
{_POST_FORMAT}
Respond EXACTLY as:
SCORE: <0-10>
---POST---
<post content>
---END---
""",
}

LOG_USER = """
Recent dev logs:
{logs}

Generate a post capturing the most interesting insight from these logs.
Source: Personal log
"""

NEWS_USER = """
Article title: {title}
Summary: {desc}
URL: {url}

Generate a post explaining why this matters to builders.
"""


class GeneratorError(Exception):
    """Raised when all AI providers fail."""


def from_logs(
    logs: list[dict],
    tone: str,
    groq_api_key: str,
    groq_model: str,
    groq_api_url: str,
    gemini_api_key: str = "",
    gemini_model: str = "gemini-1.5-flash",
) -> tuple[str, int]:
    """
    Generate a Telegram post from recent dev log entries.

    Args:
        logs: List of dicts with 'message' and 'created_at' keys.
        tone: 'builder', 'humorous', or 'technical'.
        groq_api_key: Groq API key (primary).
        groq_model: Groq model name.
        groq_api_url: Groq API endpoint URL.
        gemini_api_key: Gemini API key (fallback, optional).
        gemini_model: Gemini model name.

    Returns:
        (post_content, score) — score is 0-10 from the AI.

    Raises:
        GeneratorError: If all providers fail.
    """
    log_text = "\n".join(
        f"[{l['created_at'][:10]}] {l['message']}" for l in logs
    )
    user = LOG_USER.format(logs=log_text)
    system = SYSTEM_PROMPTS.get(tone, SYSTEM_PROMPTS["builder"])
    return _call(system, user, groq_api_key, groq_model, groq_api_url,
                 gemini_api_key, gemini_model)


def from_news(
    title: str,
    desc: str,
    url: str,
    tone: str,
    groq_api_key: str,
    groq_model: str,
    groq_api_url: str,
    gemini_api_key: str = "",
    gemini_model: str = "gemini-1.5-flash",
) -> tuple[str, int]:
    """
    Generate a Telegram post from a news article.

    Returns:
        (post_content, score) — score is 0-10 from the AI.

    Raises:
        GeneratorError: If all providers fail.
    """
    user = NEWS_USER.format(title=title, desc=desc, url=url)
    system = SYSTEM_PROMPTS.get(tone, SYSTEM_PROMPTS["builder"])
    return _call(system, user, groq_api_key, groq_model, groq_api_url,
                 gemini_api_key, gemini_model)


# ── Internal ──────────────────────────────────────────────────────────────────

def _call(
    system: str,
    user: str,
    groq_api_key: str,
    groq_model: str,
    groq_api_url: str,
    gemini_api_key: str,
    gemini_model: str,
) -> tuple[str, int]:
    """Try Groq, fall back to Gemini. Raise GeneratorError on total failure."""
    if groq_api_key:
        try:
            return _groq(system, user, groq_api_key, groq_model, groq_api_url)
        except Exception as exc:
            log.warning("Groq failed, trying Gemini: %s", exc)

    if gemini_api_key:
        try:
            return _gemini(system, user, gemini_api_key, gemini_model)
        except Exception as exc:
            log.error("Gemini also failed: %s", exc)

    raise GeneratorError("All AI providers failed.")


def _groq(system: str, user: str, api_key: str, model: str, api_url: str) -> tuple[str, int]:
    """Call Groq with retry. Returns (content, score)."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                api_url,
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
                json={"model": model,
                      "messages": [{"role": "system", "content": system},
                                   {"role": "user", "content": user}],
                      "temperature": 0.7, "max_tokens": 600},
                timeout=30,
            )
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            return _parse(raw)
        except requests.RequestException as exc:
            log.warning("Groq attempt %d/%d: %s", attempt, MAX_RETRIES, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
    raise GeneratorError(f"Groq failed after {MAX_RETRIES} attempts")


def _gemini(system: str, user: str, api_key: str, model: str) -> tuple[str, int]:
    """Call Gemini with retry. Returns (content, score)."""
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={api_key}")
    body = {"contents": [{"parts": [{"text": f"{system}\n\n{user}"}]}]}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(url, json=body, timeout=30)
            resp.raise_for_status()
            raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            return _parse(raw)
        except Exception as exc:
            log.warning("Gemini attempt %d/%d: %s", attempt, MAX_RETRIES, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
    raise GeneratorError(f"Gemini failed after {MAX_RETRIES} attempts")


def _parse(raw: str) -> tuple[str, int]:
    """Parse structured AI response. Returns (content, score)."""
    score_match = re.search(r"SCORE:\s*(\d+)", raw, re.IGNORECASE)
    score = int(score_match.group(1)) if score_match else 0
    post_match = re.search(r"---POST---\s*(.*?)\s*---END---", raw, re.DOTALL)
    content = post_match.group(1).strip() if post_match else raw.strip()
    log.debug("Parsed: score=%d len=%d", score, len(content))
    return content, score
