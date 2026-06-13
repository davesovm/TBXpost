# Contributing to TBXpost

TBXpost is a minimal, readable bot. The goal is to keep it that way.
If you want to contribute, this is the guide.

---

## What we accept

- Bug fixes with a clear description of what broke and how you fixed it
- New posting platform adapters (see "Add a new platform" in README)
- Additional RSS feed scoring improvements in `engine/fetcher.py`
- Documentation improvements
- New prompt tones in `engine/prompts.py`

We are unlikely to accept:
- New dependencies beyond the current 6 packages
- Docker or container support (by design, not in scope)
- Database migrations to non-SQLite backends
- Features that require changes to more than 2 files

---

## Setup

```bash
git clone https://github.com/davesovm/TBXpost.git
cd TBXpost
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in your test credentials
```

---

## Code style

- Python 3.11 syntax only
- Follow PEP 8 — 4-space indentation, 88-char line limit
- Every function has a docstring (one-liner is fine for simple functions)
- Use `logging` module — no `print()` statements in library code
- No hardcoded strings — all config goes through `config.py`
- No file longer than 150 lines
- Type hints on all function signatures

Example of acceptable style:

```python
def save_log(db_path: str, message: str) -> int:
    """Insert a dev log entry. Returns the new row id."""
    now = _utcnow()
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO logs (message, created_at) VALUES (?, ?)",
            (message.strip(), now),
        )
        return cur.lastrowid
```

---

## Pull request guide

1. Fork the repo and create a branch: `git checkout -b feat/my-feature`
2. Make your changes — keep each PR focused on one thing
3. Test manually: run the bot, use the command you changed, verify it works
4. Write a clear PR description:
   - What does this change?
   - Why is it needed?
   - How did you test it?
5. Open the PR — no need to update CHANGELOG, we handle that

---

## Adding a new posting platform

This is the most common contribution. The pattern is:

1. Create `poster/<platform>.py`
2. Implement a class with a `post(content: str) -> tuple[bool, Optional[str], Optional[str]]` method
3. The return type is `(success, post_id, post_url)` — match this exactly
4. Add credentials to `.env.example` with inline documentation
5. Add the new class to `config.py` for credential loading
6. Wire it into `scheduler/jobs.py` and `bot/commands.py` where Telegram is called

Do not modify `storage/db.py`, `engine/`, or `bot/handlers.py` for a new platform.

---

## Questions

Open an issue before starting large changes. It saves time for both of us.
