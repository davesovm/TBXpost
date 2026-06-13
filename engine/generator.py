"""
engine/generator.py — AI post generation.

Primary: Groq (llama-3.1-8b-instant)
Fallback: Gemini Flash

Both return the same shape: (content: str, score: int) or raise GeneratorError.
"""

import re
import time
import logging
from typing import Optional

import requests

from engine import prompts

log = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


class GeneratorError(Exception):
    """Raised when all generation attempts fail."""


def generate_from_logs(
    logs: list[dict],
    tone: str,
    groq_api_key: str,
    groq_model: str,
    groq_api_url: str,
    gemini_api_key: str = "",
    gemini_model: str = "gemini-1.5-flash",
) -> tuple[str, int]:
    """
    Generate a post from recent dev logs.

    Args:
        logs: List of log dicts with 'message' and 'created_at' keys.
        tone: One of 'builder', 'humorous', 'technical'.
        groq_api_key: Groq API key.
        groq_model: Groq model name.
        groq_api_url: Groq API endpoint.
        gemini_api_key: Gemini API key (fallback, optional).
        gemini_model: Gemini model name.

    Returns:
        (post_content, score) tuple.

    Raises:
        GeneratorError: If all providers fail.
    """
    log_text = "\n".join(
        f"[{l['created_at'][:10]}] {l['message']}" for l in logs
    )
    user_prompt = prompts.LOG_USER_TEMPLATE.format(logs=log_text)
    system_prompt = prompts.SYSTEM_PROMPTS.get(tone, prompts.SYSTEM_PROMPTS["builder"])

    return _call_with_fallback(
        system_prompt, user_prompt,
        groq_api_key, groq_model, groq_api_url,
        gemini_api_key, gemini_model,
    )


def generate_from_news(
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
    Generate a post from a news article.

    Returns:
        (post_content, score) tuple.

    Raises:
        GeneratorError: If all providers fail.
    """
    user_prompt = prompts.NEWS_USER_TEMPLATE.format(
        title=title, desc=desc, url=url
    )
    system_prompt = prompts.SYSTEM_PROMPTS.get(tone, prompts.SYSTEM_PROMPTS["builder"])

    return _call_with_fallback(
        system_prompt, user_prompt,
        groq_api_key, groq_model, groq_api_url,
        gemini_api_key, gemini_model,
    )


# ── Internal ──────────────────────────────────────────────────────────────────

def _call_with_fallback(
    system: str,
    user: str,
    groq_api_key: str,
    groq_model: str,
    groq_api_url: str,
    gemini_api_key: str,
    gemini_model: str,
) -> tuple[str, int]:
    """Try Groq first. If it fails, try Gemini. Raises GeneratorError on total failure."""
    if groq_api_key:
        try:
            return _call_groq(system, user, groq_api_key, groq_model, groq_api_url)
        except Exception as exc:
            log.warning("Groq failed, trying Gemini fallback: %s", exc)

    if gemini_api_key:
        try:
            return _call_gemini(system, user, gemini_api_key, gemini_model)
        except Exception as exc:
            log.error("Gemini fallback also failed: %s", exc)

    raise GeneratorError("All AI providers failed. Check API keys and connectivity.")


def _call_groq(
    system: str,
    user: str,
    api_key: str,
    model: str,
    api_url: str,
) -> tuple[str, int]:
    """Call Groq API with retry logic. Returns (content, score)."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                api_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 600,
                },
                timeout=30,
            )
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            return _parse_response(raw)

        except requests.RequestException as exc:
            log.warning("Groq attempt %d/%d failed: %s", attempt, MAX_RETRIES, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    raise GeneratorError(f"Groq failed after {MAX_RETRIES} attempts")


def _call_gemini(
    system: str,
    user: str,
    api_key: str,
    model: str,
) -> tuple[str, int]:
    """Call Gemini API with retry logic. Returns (content, score)."""
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    combined = f"{system}\n\nUser request:\n{user}"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                url,
                json={"contents": [{"parts": [{"text": combined}]}]},
                timeout=30,
            )
            resp.raise_for_status()
            raw = (
                resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            )
            return _parse_response(raw)

        except (requests.RequestException, KeyError) as exc:
            log.warning("Gemini attempt %d/%d failed: %s", attempt, MAX_RETRIES, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    raise GeneratorError(f"Gemini failed after {MAX_RETRIES} attempts")


def _parse_response(raw: str) -> tuple[str, int]:
    """
    Parse the structured AI response.

    Expected format:
        SCORE: <n>
        ---POST---
        <content>
        ---END---

    Returns:
        (content, score) — content is the post text, score is 0-10.
    """
    score_match = re.search(r"SCORE:\s*(\d+)", raw, re.IGNORECASE)
    score = int(score_match.group(1)) if score_match else 0

    post_match = re.search(r"---POST---\s*(.*?)\s*---END---", raw, re.DOTALL)
    content = post_match.group(1).strip() if post_match else raw.strip()

    log.debug("Parsed response: score=%d content_len=%d", score, len(content))
    return content, score
