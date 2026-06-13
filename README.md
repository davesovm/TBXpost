
# ❖ TBXpost

**A U T O M A T E D** ✦ **C U R A T E D** ✦ **P U B L I S H E D**

> *An AI-native content operating system for high-performance engineers.* 
> 
> 
> 
> 
> *Log your deep work, curate market intelligence, and maintain a consistent public presence—fully automated.*

---

### ✦ System Capabilities

| ❖ Generative Logs | ❖ Intelligence Curation |
| --- | --- |
| Transform raw, fragmented dev logs into polished, high-signal Telegram broadcasts using prompt-driven LLM orchestration (Groq/Gemini). | Continuously poll RSS feeds (HN, Dev.to), score articles for technical relevance using AI, and auto-post the top results. |
| **❖ Zero-Friction Workflow** | **❖ Extensible Architecture** |
| Post twice a week on autopilot. Everything is managed via asynchronous background jobs, keeping your terminal and attention clear. | Drop-in support for new platforms (X, LinkedIn) without refactoring the core engine. Designed for high engineering efficiency. |

---

### ✦ Architecture

```text
┌─────────────────────────────────────────────────────┐
│                     main.py                         │
│         (System Entry Point & Bootloader)           │
└──────┬──────────────┬──────────────┬────────────────┘
       │              │              │
  ┌────▼────┐   ┌─────▼─────┐  ┌────▼────────┐
  │   bot/  │   │ scheduler/│  │  storage/   │
  │commands │   │  jobs.py  │  │   db.py     │
  │handlers │   │ (APSched) │  │  (SQLite)   │
  └────┬────┘   └─────┬─────┘  └─────────────┘
       │              │
       └──────┬────────┘
              │
       ┌──────▼──────┐         ┌──────────────┐
       │   engine/   │         │   poster/    │
       │ generator   │         │ telegram.py  │
       │  fetcher    │         │ (+ future:   │
       │  prompts    │         │  x.py,       │
       └─────────────┘         │  linkedin.py)│
                               └──────────────┘

```

---

### ✦ Quick Start

Boot the system locally in under two minutes.

```bash
# 1. Clone & enter repository
git clone https://github.com/davesovm/TBXpost.git
cd TBXpost

# 2. Initialize isolated environment
python -m venv venv
source venv/bin/activate   

# 3. Install core dependencies
pip install -r requirements.txt

# 4. Provision environment keys
cp .env.example .env
# Inject TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL, TELEGRAM_ADMIN_ID, and GROQ_API_KEY

# 5. Ignite
python main.py

```

*Verify the telemetry by sending /status to your bot via Telegram.*

---

### ✦ Command Interface

**Authorization:** Strict access control. Commands execute exclusively for the defined `TELEGRAM_ADMIN_ID`.

| Command | Action | Example |
| --- | --- | --- |
| /log | Persist a raw development update. | `/log optimizing token usage in RAG pipeline` |
| /status | Query the last 5 operational logs. | `/status` |
| /generate | Compile a drafted post from recent logs. | `/generate builder` |
| /post_now | Force-publish the latest generated draft. | `/post_now` |
| /news | Force-fetch, score, and broadcast news. | `/news` |

*Available Generation Tones:* `<kbd>builder</kbd>` (default), `<kbd>humorous</kbd>`, `<kbd>technical</kbd>`

---

### ✦ Configuration Matrix

| Env Variable | Req | Default | Protocol / Purpose |
| --- | --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | ✅ | — | Bot authentication token via @BotFather |
| `TELEGRAM_CHANNEL` | ✅ | — | Target broadcast channel (e.g., `@mychannel`) |
| `TELEGRAM_ADMIN_ID` | ✅ | — | Authorized administrator ID |
| `GROQ_API_KEY` | ✅ | — | Primary LLM inference key |
| `GROQ_MODEL` | ❌ | `llama-3.1-8b-instant` | Target model specification |
| `GEMINI_API_KEY` | ❌ | — | Fallback LLM inference key |
| `GEMINI_MODEL` | ❌ | `gemini-1.5-flash` | Fallback model specification |
| `POST_DAYS` | ❌ | `mon,thu` | Execution schedule constraints |
| `POST_HOUR` | ❌ | `9` | Execution UTC hour block |
| `POST_MINUTE` | ❌ | `0` | Execution UTC minute block |
| `NEWS_MIN_SCORE` | ❌ | `7` | Minimum AI relevancy threshold (0-10) |

---

### ✦ Extensibility: Adding Platforms

TBXpost is engineered for seamless expansion. Integrating networks like X or LinkedIn requires **zero modifications** to the existing core.

**1. Define the Poster Class (`poster/x.py`)**

```python
import logging
from typing import Optional

log = logging.getLogger(__name__)

class XPoster:
    def __init__(self, api_key: str, api_secret: str):
        pass

    def post(self, content: str) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Returns (success, post_id, post_url). Must not raise exceptions.
        """
        pass

```

**2. Map Credentials**
Inject your credentials into `.env` and map them in `config.py`:

```python
x_api_key: str = os.environ.get("X_API_KEY", "")

```

**3. Execute Injection**
Call your new class directly from `scheduler/jobs.py` or `bot/commands.py`:

```python
from poster.x import XPoster
x_client = XPoster(cfg.x_api_key, cfg.x_api_secret)
x_client.post(content)

```

---

### ✦ Deployment (Render Free Tier)

Designed to run efficiently on ephemeral compute:

1. Connect this repository to **[Render](https://render.com)** as a **Web Service**.
2. Set Environment to `Python 3`.
3. Build command: `<kbd>pip install -r requirements.txt</kbd>`
4. Start command: `<kbd>python main.py</kbd>`
5. Inject your `.env` variables and Deploy.

*Note: Render's free tier spins down idle instances. However, TBXpost's `APScheduler` async mode ensures the process remains highly responsive to webhook commands and reliably executes scheduled bi-weekly background jobs.*

---