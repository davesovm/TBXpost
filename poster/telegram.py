"""
poster/telegram.py — Telegram channel posting.

Implements the BasePoster interface.
To add a new platform (X, LinkedIn), create a new file that implements
the same post() method signature. Zero changes needed here or anywhere else.
"""

import logging
import time
from typing import Optional

import requests

log = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


class TelegramPoster:
    """
    Posts messages to a Telegram channel.

    Usage:
        poster = TelegramPoster(token="...", channel="@mychannel")
        success, message_id, post_url = poster.post("Hello world")
    """

    def __init__(self, token: str, channel: str) -> None:
        """
        Args:
            token: Telegram bot token from @BotFather.
            channel: Channel username (e.g. '@mychannel') or chat_id.
        """
        self.token = token
        self.channel = channel
        self._base = f"https://api.telegram.org/bot{token}"

    def post(self, content: str) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Send a message to the configured Telegram channel.

        Args:
            content: The message text to post.

        Returns:
            (success, message_id, post_url)
            post_url is the direct t.me link if available.
            Never raises.
        """
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = requests.post(
                    f"{self._base}/sendMessage",
                    json={
                        "chat_id": self.channel,
                        "text": content,
                        "disable_web_page_preview": False,
                    },
                    timeout=20,
                )
                data = resp.json()

                if data.get("ok"):
                    msg_id = str(data["result"]["message_id"])
                    # Build public link only for public channels (starts with @)
                    post_url = None
                    if self.channel.startswith("@"):
                        handle = self.channel.lstrip("@")
                        post_url = f"https://t.me/{handle}/{msg_id}"
                    log.info("Telegram post sent: %s", post_url or msg_id)
                    return True, msg_id, post_url

                error_desc = data.get("description", "unknown error")
                log.warning(
                    "Telegram attempt %d/%d failed: %s",
                    attempt, MAX_RETRIES, error_desc,
                )

            except requests.RequestException as exc:
                log.warning(
                    "Telegram attempt %d/%d — request error: %s",
                    attempt, MAX_RETRIES, exc,
                )

            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

        log.error("Telegram posting failed after %d attempts", MAX_RETRIES)
        return False, None, None

    def test_connection(self) -> bool:
        """
        Verify the bot token is valid by calling getMe.
        Returns True if the bot responds correctly.
        """
        try:
            resp = requests.get(f"{self._base}/getMe", timeout=10)
            ok = resp.json().get("ok", False)
            if ok:
                username = resp.json()["result"].get("username", "")
                log.info("Telegram connection OK: @%s", username)
            return ok
        except Exception as exc:
            log.error("Telegram connection test failed: %s", exc)
            return False
