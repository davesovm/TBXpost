
![TBXpost Interface](https://github.com/user-attachments/assets/527177b7-72f1-412e-b33e-29162196a5b6)


# TBXpost

![Python](https://img.shields.io/badge/python-3.11-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Last Commit](https://img.shields.io/github/last-commit/davesovm/TBXpost)

A personal content OS for developers — logs dev work, curates tech news, generates posts using AI, and auto-posts to Telegram twice a day. Zero cloud cost. Zero server. Just GitHub Actions + your local machine.


---

## What it does

TBXpost is split into two engines that work independently:

**Broadcast engine** (GitHub Actions — free, serverless)
Wakes up at 06:00 and 18:00 UTC every day. Fetches the best developer news from RSS feeds, runs it through Groq AI for curation, posts to your Telegram channel, and logs it to `broadcast_history.md`. Total compute per run: ~30 seconds.

**Interactive engine** (your local machine — instant, private)
Runs as a background `systemd` daemon. Responds to `/log`, `/status`, `/generate`, `/post_now`, `/news` commands instantly. Your dev logs never leave your machine until you authorize a post.

---

## Architecture

```
GitHub Actions (free)          Your Linux machine (local)
──────────────────────         ──────────────────────────
broadcast.yml                  bot/run_bot.py (systemd)
  ↓ 06:00 + 18:00 UTC            ↓ always running
scheduler/run_jobs.py          bot/commands.py
  ↓                              ↓
core/engine.py  ←──────────→  core/engine.py  (shared)
core/telegram.py ←─────────→  core/telegram.py (shared)
engine/fetcher.py              storage/db.py (local SQLite)
  ↓                              ↓
@sovm00 channel                @sovm00 channel
broadcast_history.md           tbxpost.db (your machine)
```

---

## Quick start — local bot (5 minutes)

```bash
# 1. Clone
git clone https://github.com/davesovm/TBXpost.git
cd TBXpost

# 2. Virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies (4 packages)
pip install -r requirements.txt

# 4. Configure
cp .env.example .env
nano .env   # fill in the 4 required values

# 5. Run
python bot/run_bot.py
```

Send `/status` to your bot on Telegram. It responds instantly.

---

## Quick start — GitHub Actions broadcast (3 minutes)

Add 3 secrets to your GitHub repo:

**github.com/davesovm/TBXpost → Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value |
|--------|-------|
| `TELEGRAM_BOT_TOKEN` | your bot token |
| `TELEGRAM_CHANNEL` | `@yourchannel` |
| `GROQ_API_KEY` | your Groq key |

That's it. The `broadcast.yml` workflow is already in the repo. It fires automatically at 06:00 and 18:00 UTC. Test it immediately: **Actions → TBXpost Broadcast → Run workflow**.

---

## Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/log [message]` | Save a dev update to local SQLite | `/log shipped OAuth module` |
| `/status` | Show your last 5 dev logs | `/status` |
| `/generate [tone]` | Generate a post from recent logs | `/generate humorous` |
| `/post_now` | Post the latest generated post to the channel | `/post_now` |
| `/news` | Fetch top news and post it immediately | `/news` |

All commands are admin-only. Only `TELEGRAM_ADMIN_ID` can run them.

Tones for `/generate`: `builder` (default), `humorous`, `technical`

---

## Broadcast schedule

| Time | What happens |
|------|-------------|
| 06:00 UTC | Fetch RSS → Groq curation → post to channel → log to `broadcast_history.md` |
| 18:00 UTC | Fetch RSS → Groq curation → post to channel → log to `broadcast_history.md` |

GitHub Actions free tier: 2,000 min/month. Each run takes ~30 seconds. Cost: effectively zero.

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
| `RSS_FEEDS` | ❌ | HN + Dev.to | Comma-separated RSS feed URLs |
| `NEWS_MIN_SCORE` | ❌ | `7` | Min AI quality score to post (0–10) |
| `DB_PATH` | ❌ | `tbxpost.db` | SQLite database file path (local only) |

---

## Run as a background service (systemd)

Install the bot as a silent daemon that starts automatically on login:

```bash
# 1. Edit paths in tbxpost.service if needed
nano tbxpost.service

# 2. Install
mkdir -p ~/.config/systemd/user
cp tbxpost.service ~/.config/systemd/user/tbxpost.service

# 3. Enable and start
systemctl --user enable tbxpost
systemctl --user start tbxpost

# 4. Check it's running
systemctl --user status tbxpost

# 5. Follow live logs
journalctl --user -u tbxpost -f
```

The bot restarts automatically on failure (`Restart=on-failure`). It reads `.env` for all secrets.

---

## Add a new posting platform in 30 minutes

No changes to existing files needed. Create `poster/x.py`:

```python
# poster/x.py
import logging
from typing import Optional
log = logging.getLogger(__name__)

class XPoster:
    def __init__(self, api_key: str, api_secret: str): ...

    def post(self, content: str) -> tuple[bool, Optional[str], Optional[str]]:
        """Returns (success, post_id, post_url). Never raises."""
        ...
```

Add credentials to `.env.example`, load in `config.py`, call from `bot/commands.py` alongside the existing Telegram call. Done.

---

## Project structure

```
TBXpost/
├── core/
│   ├── engine.py           # Groq + Gemini AI generation (shared)
│   └── telegram.py         # Telegram post + retry (shared)
├── bot/
│   ├── commands.py         # /log /status /generate /post_now /news
│   ├── handlers.py         # command registration
│   └── run_bot.py          # local daemon entry point ← run this
├── engine/
│   └── fetcher.py          # RSS fetch + keyword scoring
├── scheduler/
│   └── run_jobs.py         # GitHub Actions broadcast script
├── storage/
│   └── db.py               # all SQLite operations (local only)
├── .github/workflows/
│   └── broadcast.yml       # 2x/day cron workflow
├── config.py               # ENV loading
├── tbxpost.service         # systemd unit file
├── broadcast_history.md    # auto-updated by GitHub Actions
├── requirements.txt        # 4 packages
├── .env.example
├── MIGRATION.md
└── CONTRIBUTING.md
```

---

## Database schema

Three tables, auto-created on first run. Local to your machine only.

```sql
logs            — id, message, created_at
posts           — id, content, tone, source_type, created_at
posting_history — id, post_id, platform, message_id, post_url, success, error, posted_at
```

All DB operations in `storage/db.py`. Nothing else touches the database.

---

## License

MIT — see [LICENSE](LICENSE)
