"""
storage/db.py — All SQLite operations.

Three tables: logs, posts, posting_history.
Schema is auto-created on first run.
Nothing outside this file touches the database.
"""

import sqlite3
import logging
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)


def _connect(db_path: str) -> sqlite3.Connection:
    """Open a connection with row_factory set to Row for dict-like access."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init(db_path: str) -> None:
    """
    Create all tables if they don't exist.
    Safe to call on every startup.
    """
    with _connect(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS logs (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                message    TEXT    NOT NULL,
                created_at TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS posts (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                content      TEXT    NOT NULL,
                tone         TEXT    NOT NULL DEFAULT 'builder',
                source_type  TEXT    NOT NULL DEFAULT 'log',
                created_at   TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS posting_history (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id      INTEGER,
                platform     TEXT    NOT NULL,
                message_id   TEXT,
                post_url     TEXT,
                success      INTEGER NOT NULL DEFAULT 0,
                error        TEXT,
                posted_at    TEXT    NOT NULL,
                FOREIGN KEY (post_id) REFERENCES posts(id)
            );
        """)
    log.info("Database initialised at %s", db_path)


# ── Logs ──────────────────────────────────────────────────────────────────────

def save_log(db_path: str, message: str) -> int:
    """
    Insert a dev log entry.
    Returns the new row id.
    """
    now = _utcnow()
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO logs (message, created_at) VALUES (?, ?)",
            (message.strip(), now),
        )
        log.debug("Log saved: id=%s", cur.lastrowid)
        return cur.lastrowid


def get_recent_logs(db_path: str, limit: int = 5) -> list[dict]:
    """Return the most recent dev log entries as a list of dicts."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── Posts ─────────────────────────────────────────────────────────────────────

def save_post(
    db_path: str,
    content: str,
    tone: str = "builder",
    source_type: str = "log",
) -> int:
    """
    Save a generated post to the posts table.
    Returns the new row id.
    """
    now = _utcnow()
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO posts (content, tone, source_type, created_at) VALUES (?, ?, ?, ?)",
            (content.strip(), tone, source_type, now),
        )
        log.debug("Post saved: id=%s tone=%s", cur.lastrowid, tone)
        return cur.lastrowid


def get_latest_post(db_path: str) -> Optional[dict]:
    """Return the most recently generated post, or None if none exist."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM posts ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


# ── Posting history ───────────────────────────────────────────────────────────

def record_posting(
    db_path: str,
    post_id: Optional[int],
    platform: str,
    success: bool,
    message_id: Optional[str] = None,
    post_url: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    """Record the result of a posting attempt to any platform."""
    now = _utcnow()
    with _connect(db_path) as conn:
        conn.execute(
            """INSERT INTO posting_history
               (post_id, platform, message_id, post_url, success, error, posted_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (post_id, platform, message_id, post_url, int(success), error, now),
        )
    log.debug("Posting recorded: platform=%s success=%s", platform, success)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _utcnow() -> str:
    """Return the current UTC time as an ISO string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
