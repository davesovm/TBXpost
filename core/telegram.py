"""
core/telegram.py — Shared Telegram posting logic.

Used by both bot/ (interactive) and scheduler/ (broadcast).
Stateless — no database dependency.
"""

import logging
import time
from typing import Optional

import requests

log = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


def send_message(
    token: str,
    channel: str,
    text: str,
) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Send a message to a Telegram channel with retry logic.

    Args:
        token: Telegram bot token.
        channel: Channel username (e.g. '@mychannel') or numeric chat_id.
        text: Message content to post.

    Returns:
        (success, message_id, post_url)
        post_url is the direct t.me link for public channels.
        Never raises.
    """
    base = f"https://api.telegram.org/bot{token}"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                f"{base}/sendMessage",
                json={
                    "chat_id": channel,
                    "text": text,
                    "disable_web_page_preview": False,
                },
                timeout=20,
            )
            data = resp.json()

            if data.get("ok"):
                msg_id = str(data["result"]["message_id"])
                post_url = None
                if channel.startswith("@"):
                    handle = channel.lstrip("@")
                    post_url = f"https://t.me/{handle}/{msg_id}"
                log.info("Telegram message sent: %s", post_url or msg_id)
                return True, msg_id, post_url

            log.warning(
                "Telegram attempt %d/%d: %s",
                attempt, MAX_RETRIES,
                data.get("description", "unknown error"),
            )

        except requests.RequestException as exc:
            log.warning("Telegram attempt %d/%d error: %s", attempt, MAX_RETRIES, exc)

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)

    log.error("Telegram posting failed after %d attempts", MAX_RETRIES)
    return False, None, None


def verify_token(token: str) -> bool:
    """
    Check that a bot token is valid by calling getMe.
    Returns True if the bot responds correctly.
    """
    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{token}/getMe",
            timeout=10,
        )
        ok = resp.json().get("ok", False)
        if ok:
            log.info("Token valid: @%s", resp.json()["result"].get("username", ""))
        return ok
    except Exception as exc:
        log.error("Token verification failed: %s", exc)
        return False
