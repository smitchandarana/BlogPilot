# BlogPilot — LinkedIn AI Growth Engine

Local-first Python application with React UI for automated LinkedIn engagement, AI comment generation, lead capture, and email enrichment.

---

## Quick Start

### Prerequisites

- **Python 3.11+** (tested with 3.14)
- **Node.js 18+**
- **Groq API key** — free at [console.groq.com](https://console.groq.com)

### Installation

```bash
# Clone
git clone <repo-url> && cd BlogPilot

# Backend dependencies
pip install -r requirements.txt

# Playwright browser (first time only)
playwright install chromium

# Frontend dependencies
cd ui && npm install && cd ..
```

### Running

```bash
# Terminal 1 — Backend (from project root)
python -m uvicorn backend.main:app --port 8000

# Terminal 2 — Frontend
cd ui && npm run dev
```

Open **http://localhost:3000** in your browser.

Or use the single-command launcher:
```bash
python launcher.py
```

### First-Time Setup

1. Open the **Settings** page in the UI
2. Paste your **Groq API key** and click Save Key
3. Run the credential setup for LinkedIn (optional — needed for automation):
   ```bash
   python -m backend.utils.setup_credentials
   ```
4. Configure your targeting topics on the **Topics** page
5. Click **Start Engine** on the Dashboard

---

## Configuration

All settings live in `config/settings.yaml`. The engine hot-reloads this file — no restart needed when you change settings.

Key sections:
- **daily_budget** — per-action daily limits (likes: 30, comments: 12, connections: 15, etc.)
- **rate_limits** — per-hour caps to avoid LinkedIn detection
- **delays** — min/max random delays between actions (seconds)
- **ai** — Groq model, temperature, max tokens
- **feed_engagement** — mode (smart/like_only/comment_only), min relevance score
- **circuit_breaker** — error threshold, auto-pause duration

Settings can also be changed via the Settings UI — changes persist to the YAML file.

---

## API Keys & Secrets

| Key | How to set | Required |
|---|---|---|
| Groq API key | Settings UI or `config/.secrets/groq.json` | Yes (for AI features) |
| LinkedIn credentials | `python -m backend.utils.setup_credentials` | Yes (for automation) |
| Hunter.io API key | `config/.secrets/hunter.json` | No (optional email enrichment) |

All secrets are stored encrypted (PBKDF2 + Fernet). Never commit the `config/.secrets/` directory.

---

## Project Structure

```
BlogPilot/
├── backend/
│   ├── main.py           ← FastAPI app entry point
│   ├── api/              ← REST + WebSocket endpoints (8 routers)
│   ├── core/             ← Engine runtime (state machine, scheduler, workers, pipeline)
│   ├── automation/       ← Playwright browser automation (feed, profiles, interactions)
│   ├── ai/               ← Groq AI layer (scoring, comment/post/note/reply generation)
│   ├── growth/           ← Viral detection, campaigns, engagement strategy, topic rotation
│   ├── enrichment/       ← Email finding (DOM, patterns, SMTP, Hunter.io)
│   ├── storage/          ← SQLite + SQLAlchemy ORM
│   └── utils/            ← Logger, encryption, config loader, lock file
├── ui/                   ← React + Vite + Tailwind (port 3000)
│   └── src/
│       ├── pages/        ← 10 page components
│       ├── components/   ← Reusable UI components
│       ├── hooks/        ← useEngine, useWebSocket
│       └── api/          ← Axios client
├── prompts/              ← Editable AI prompt templates
├── config/
│   └── settings.yaml     ← All configuration
├── tests/                ← 65 tests (pytest)
├── launcher.py           ← Single-command entry point
├── run_tests.py          ← Master test runner with config checks
└── blogpilot.spec        ← PyInstaller build config
```

---

## UI Pages

| Page | Route | Description |
|---|---|---|
| Dashboard | `/` | Engine status, budget bars, live activity feed |
| Engine Control | `/control` | Module toggles, activity window, schedule settings |
| Topics | `/topics` | Target topics, hashtags, blacklist, watchlists |
| Feed Engagement | `/feed` | Engagement mode, recent posts, comment history |
| Content Studio | `/content` | AI post generator, scheduler, publish queue |
| Campaigns | `/campaigns` | Multi-step outreach sequences |
| Leads | `/leads` | Lead table, email status, CSV export |
| Analytics | `/analytics` | Charts, top topics, campaign funnel |
| Prompt Editor | `/prompts` | Edit AI prompts with live test panel |
| Settings | `/settings` | API keys, rate limits, delays, browser config |

---

## Engine Pipeline

1. Scheduler triggers feed scan
2. Feed scanner extracts posts from LinkedIn
3. Deduplicate against seen posts in DB
4. AI relevance scoring (Groq LLM)
5. Viral velocity check
6. Engagement strategy decision (like / comment / skip)
7. AI comment generation
8. Human-like random delay
9. Execute action via Playwright
10. Log to DB + push WebSocket event to UI

---

## Testing

```bash
# Run all tests (94 tests)
pytest tests/ -v

# Quick run (skip E2E)
pytest tests/ -v -k "not test_e2e"

# Config validation + full test suite
python run_tests.py

# Config check only
python run_tests.py --check
```

---

## Building (Standalone EXE)

```bash
# Build frontend first
cd ui && npm run build && cd ..

# Package with PyInstaller
pyinstaller blogpilot.spec
# Output: dist/BlogPilot/BlogPilot.exe
```

---

## Safety Features

- **Daily budget caps** — hard limits on all action types
- **Hourly rate limiting** — sliding window per action type
- **Circuit breaker** — auto-pauses engine on repeated errors, auto-resumes after cooldown
- **Human-like delays** — gaussian-distributed random timing between actions
- **Single instance lock** — prevents duplicate engines from running
- **Encrypted credentials** — PBKDF2 key derivation + Fernet symmetric encryption
- **CAPTCHA detection** — pauses engine and alerts UI for manual intervention

---

## Phase 2

Phase 1 is complete (Sprints 1–8, all milestones M1–M6 achieved). The remaining gate is M7 runtime validation — run `python scripts/m7_validate.py` after a 4-hour unattended engine run.

Once M7 passes, Phase 2 (Chrome Extension) begins. See TASKS.md for the full task list and REVIEW_AND_PLAN.txt for the week-by-week roadmap.
