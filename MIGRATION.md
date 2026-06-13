# MIGRATION.md — Switch from old bot to TBXpost

This document covers the exact steps to migrate from the existing `fetch_news.py`
embedded in the portfolio repo to the standalone TBXpost bot — with zero downtime.

---

## Strategy

The old bot keeps running on its existing token throughout testing.
TBXpost runs on a **separate test token** until all manual tests pass.
You switch tokens only at the final step.

---

## Phase 1 — Set up TBXpost with a test token

### 1.1 Create a test bot

- Open Telegram → search `@BotFather`
- Send `/newbot`
- Name it something like "DevPulse Test"
- Copy the token — this is your `TEST_TELEGRAM_BOT_TOKEN`

### 1.2 Clone and configure

```bash
git clone https://github.com/davesovm/TBXpost.git
cd TBXpost
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:

```env
TELEGRAM_BOT_TOKEN=<TEST_TELEGRAM_BOT_TOKEN>
TELEGRAM_CHANNEL=@sovm00
TELEGRAM_ADMIN_ID=<your Telegram user ID>
GROQ_API_KEY=<your Groq key from existing .env>
```

### 1.3 Start TBXpost

```bash
python main.py
```

You should see: `TBXpost is running.`

---

## Phase 2 — Manual testing checklist

Run each command in Telegram with your test bot. Check them off:

- [ ] `/status` — returns "No logs yet" (correct for fresh DB)
- [ ] `/log built the OAuth flow` — returns "✅ Logged (#1)"
- [ ] `/log fixed rate limiting bug` — returns "✅ Logged (#2)"
- [ ] `/status` — shows 2 logs with dates
- [ ] `/generate` — returns a generated post (may take ~5 seconds)
- [ ] `/generate humorous` — returns a post in humorous tone
- [ ] `/generate technical` — returns a post in technical tone
- [ ] `/post_now` — posts to `@sovm00`, returns "✅ Posted to channel!"
  - Verify the post appears in your channel
- [ ] `/news` — fetches RSS, generates and posts a news item
  - Verify it appears in `@sovm00`

All 9 checks must pass before proceeding.

---

## Phase 3 — Switch to production token

### 3.1 Stop TBXpost

```bash
Ctrl+C
```

### 3.2 Stop the old bot

In the portfolio repo, disable or pause the GitHub Action:

```
GitHub → sovm-s repo → Actions → "Update News Widget" → disable workflow
```

Wait 2 minutes to confirm no scheduled runs are in flight.

### 3.3 Update .env with the real token

Edit `.env` in TBXpost:

```env
# Replace the test token with the production token
TELEGRAM_BOT_TOKEN=<PRODUCTION_BOT_TOKEN>
```

The production token is the one currently used by `fetch_news.py` in the
portfolio repo (set in GitHub Secrets as `TELEGRAM_BOT_TOKEN`).

### 3.4 Restart TBXpost

```bash
python main.py
```

### 3.5 Verify production

- Send `/status` — should respond correctly
- Send `/news` — should post a real news item to `@sovm00`
- Confirm post appears in the channel with the correct bot attribution

---

## Phase 4 — Deploy to Render

### 4.1 Push TBXpost to GitHub

```bash
git remote set-url origin https://github.com/davesovm/TBXpost.git
git add .
git commit -m "initial production setup"
git push -u origin main
```

### 4.2 Create Render Web Service

1. [render.com](https://render.com) → New → Web Service
2. Connect your GitHub repo
3. Settings:
   - Environment: Python 3
   - Build command: `pip install -r requirements.txt`
   - Start command: `python main.py`
4. Environment variables — add all variables from your `.env` file
5. Click **Deploy**

### 4.3 Verify on Render

- Watch deploy logs — look for `TBXpost is running.`
- Send `/status` from Telegram — should respond
- Check Render logs for any errors

---

## Phase 5 — Clean up

Once TBXpost is stable on Render for 48 hours:

- Delete the test bot via `@BotFather` → `/deletebot`
- Remove `fetch_news.py` from the portfolio repo (or leave it — it won't conflict)
- Archive the old GitHub Action or delete it
- Update `llms.txt` in the portfolio repo to point to the new bot repo URL

---

## Rollback plan

If something goes wrong after switching to the production token:

1. Stop TBXpost (Render → Manual Deploy → Cancel, or Ctrl+C locally)
2. Re-enable the old GitHub Action in the portfolio repo
3. The old `fetch_news.py` will pick up on the next scheduled run

The old bot does not need the same token — it uses the GitHub Action environment,
which still has the production token in Secrets. No token changes needed to roll back.

---

## Token reference

| Variable | Phase 1–2 | Phase 3+ |
|----------|-----------|----------|
| `TELEGRAM_BOT_TOKEN` | Test bot token | Production bot token |
| `TELEGRAM_CHANNEL` | `@sovm00` | `@sovm00` |
| `TELEGRAM_ADMIN_ID` | Your user ID | Your user ID |

---

## Data migration (optional)

The old system stores no persistent state (only `news.json` — a flat file).
TBXpost uses SQLite for logs and post history.

If you want to pre-load your existing news.json article as a seed:

```python
# Run once from the TBXpost root
import json
from storage import db

with open("../sovm-s/news.json") as f:
    article = json.load(f)

db.init("devpulse.db")
db.save_post("devpulse.db", article["portfolio_preview"], tone="builder", source_type="news")
print("Seed post imported.")
```

This is entirely optional — the bot works fine with an empty database.
