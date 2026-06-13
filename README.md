# TBXpost

![Python](https://img.shields.io/badge/python-3.11-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Last Commit](https://img.shields.io/github/last-commit/davesovm/TBXpost)

A personal content OS for developers — logs dev work, curates tech news, generates posts using AI, and auto-posts to Telegram twice a day. Clone it, fill in `.env`, run `python main.py`. Done in under 10 minutes.

---

## What it does

TBXpost turns your raw dev logs into polished Telegram posts using Groq AI. It fetches the best developer news from RSS feeds twice a day (06:00 and 18:00 UTC), scores it for relevance, and posts it to your channel automatically. Every piece of content passes through a prompt-driven editorial layer before it goes public. You keep full control via interactive bot commands — all from your own Telegram chat.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        main.py                              │
│          (Render entry point — bot + scheduler)             │
└──────┬──────────────────┬──────────────┬────────────────────┘
       │                  │              │
  ┌────▼────┐       ┌─────▼─────┐  ┌────▼────────┐
  │   bot/  │       │ APScheduler│  │  storage/   │
  │commands │       │ 06:00 UTC  │  │  db.py      │
  │handlers │       │ 18:00 UTC  │  │  (SQLite)   │
  └────┬────┘       └─────┬──────┘  └─────────────┘
       │                  │
       └──────┬────────────┘
              │
       ┌──────▼──────────────────────┐
       │         core/               │
       │  engine.py  (Groq+Gemini)   │
       │  telegram.py (post+retry)   │
       └──────┬──────────────────────┘
              │
       ┌──────▼──────────────┐
       │    engine/          │
       │  fetcher.py (RSS)   │
       └─────────────────────┘

  Also available: bot/run_bot.py — run locally as systemd daemon
  Also available: scheduler/run_jobs.py — stateless GitHub Actions broadcast
```

---

## Quick start

```bash
# 1. Clone
git clone https://github.com/davesovm/TBXpost.git
cd TBXpost

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure
cp .env.example .env
# Edit .env — fill in TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL,
#              TELEGRAM_ADMIN_ID, GROQ_API_KEY

# 5. Run
python main.py
```

Send `/status` in your Telegram chat with the bot to confirm it's live.

---

## Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/log [message]` | Save a dev update to the local database | `/log shipped OAuth module` |
| `/status` | Show your last 5 dev logs | `/status` |
| `/generate [tone]` | Generate a post from recent logs | `/generate humorous` |
| `/post_now` | Post the latest generated post to the channel | `/post_now` |
| `/news` | Fetch top news and post it immediately | `/news` |

All commands are admin-only. Only `TELEGRAM_ADMIN_ID` can run them.

Tones for `/generate`: `builder` (default), `humorous`, `technical`

---

## Broadcast schedule

TBXpost auto-posts twice a day:

| Time | What happens |
|------|-------------|
| 06:00 UTC | Fetch top RSS article → Groq curation → post to channel |
| 18:00 UTC | Fetch top RSS article → Groq curation → post to channel |

Schedule is handled by APScheduler inside `main.py` when running on Render.
If you prefer GitHub Actions instead, see `scheduler/run_jobs.py` and `.github/workflows/broadcast.yml`.

---

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | ✅ | — | Bot token from @BotFather |
| `TELEGRAM_CHANNEL` | ✅ | — | Channel to post to, e.g. `@mychannel` |
| `TELEGRAM_ADMIN_ID` | ✅ | — | Your Telegram user ID (from @userinfobot) |
| `GROQ_API_KEY` | ✅ | — | Groq API key (free at console.groq.com) |
| `GROQ_MODEL` | ❌ | `llama-3.1-8b-instant` | Groq model name |
| `GEMINI_API_KEY` | ❌ | — | Gemini key — fallback if Groq fails |
| `GEMINI_MODEL` | ❌ | `gemini-1.5-flash` | Gemini model for fallback |
| `TIMEZONE` | ❌ | `UTC` | Scheduler timezone |
| `RSS_FEEDS` | ❌ | HN + Dev.to | Comma-separated RSS feed URLs |
| `NEWS_MIN_SCORE` | ❌ | `7` | Min AI quality score to post (0–10) |
| `DB_PATH` | ❌ | `tbxpost.db` | SQLite database file path |

---

## Deploy on Render (free tier)

`render.yaml` is included — Render reads it automatically.

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → **New → Blueprint**
3. Connect your GitHub repo → select `davesovm/TBXpost`
4. Render detects `render.yaml` and pre-fills build/start commands
5. Add these 4 secrets under **Environment → Add Environment Variable**:

```
TELEGRAM_BOT_TOKEN   → your bot token
TELEGRAM_CHANNEL     → @yourchannel
TELEGRAM_ADMIN_ID    → your Telegram user ID
GROQ_API_KEY         → your Groq key
```

6. Click **Deploy** — watch logs for `TBXpost is running.`

Render runs this as a **Worker** (not a web service) — no HTTP port, no spin-down issue. APScheduler fires the broadcast jobs at 06:00 and 18:00 UTC inside the running process.

---

## Run locally as a background daemon (Linux / macOS)

If you prefer to run the interactive bot on your own machine:

```bash
# 1. Edit the paths in tbxpost.service to match your system
nano tbxpost.service

# 2. Install and enable
cp tbxpost.service ~/.config/systemd/user/tbxpost.service
systemctl --user enable tbxpost
systemctl --user start tbxpost

# 3. Check status
systemctl --user status tbxpost
journalctl --user -u tbxpost -f
```

The bot starts automatically when you log in and restarts on failure.

---

## Add a new posting platform in 30 minutes

Zero changes to existing files. Create `poster/x.py`:

```python
# poster/x.py
import logging
from typing import Optional

log = logging.getLogger(__name__)

class XPoster:
    def __init__(self, api_key: str, api_secret: str):
        ...

    def post(self, content: str) -> tuple[bool, Optional[str], Optional[str]]:
        """Returns (success, post_id, post_url). Never raises."""
        ...
```

Add credentials to `.env.example`, load them in `config.py`, call `XPoster.post()` from `bot/commands.py` or `main.py` alongside the existing Telegram call. Done.

---

## Project structure

```
TBXpost/
├── core/
│   ├── engine.py        # Groq + Gemini AI generation (shared)
│   └── telegram.py      # Telegram post + retry (shared)
├── bot/
│   ├── commands.py      # /log /status /generate /post_now /news
│   ├── handlers.py      # command registration
│   └── run_bot.py       # local daemon entry point
├── engine/
│   └── fetcher.py       # RSS fetch + keyword scoring
├── scheduler/
│   └── run_jobs.py      # stateless GitHub Actions broadcast script
├── storage/
│   └── db.py            # all SQLite operations
├── .github/workflows/
│   └── broadcast.yml    # 2x/day cron (alternative to Render)
├── config.py            # ENV loading
├── main.py              # Render entry point (bot + APScheduler)
├── render.yaml          # Render Blueprint config
├── tbxpost.service      # systemd unit file for local daemon
├── broadcast_history.md # auto-updated post log
├── requirements.txt
├── .env.example
├── MIGRATION.md
└── CONTRIBUTING.md
```

---

## Database schema

Three tables, auto-created on first run.

```sql
logs            — id, message, created_at
posts           — id, content, tone, source_type, created_at
posting_history — id, post_id, platform, message_id, post_url, success, error, posted_at
```

All DB operations live in `storage/db.py`. Nothing else touches the database.

---

## License

MIT — see [LICENSE](LICENSE)
