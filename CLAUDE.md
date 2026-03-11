# LinkedIn AI Growth Engine

Local-first Python application with React UI for automated LinkedIn engagement, AI comment generation, lead capture, and email enrichment. Converts to Chrome Extension in Phase 2.

Read these files before doing anything:
- @CONTEXT.md — ⚡ COMPRESSED reference (read this first, not ARCHITECTURE.md — 80% fewer tokens)
- @BUILD_PROMPTS.md — step-by-step build prompts per sprint, with model recommendations
- @TASKS.md — what is built, what is missing, what to build next
- @PROMPTS.md — all AI prompt templates used by the system
- @TOPICS.md — default targeting topics and hashtags
- @config/settings.yaml — all configuration values

> 💡 Token tip: Always start sessions with "Read CONTEXT.md" not ARCHITECTURE.md.
> ARCHITECTURE.md has full detail — use it only when CONTEXT.md isn't enough.

---

## Commands

```bash
# Backend
cd backend && pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
cd ui && npm install
npm run dev  # runs on port 3000

# Database
python -m storage.database  # initialise SQLite schema

# Run tests
pytest tests/ -v

# Single module test
pytest tests/test_feed_scanner.py -v
```

---

## Architecture Summary

```
ui/          → React + Vite + Tailwind (localhost:3000)
backend/
  api/       → FastAPI routes
  core/      → Engine runtime (scheduler, queue, workers, state)
  automation/→ Playwright browser layer
  ai/        → Groq API layer
  growth/    → Viral detection, campaigns, strategy
  enrichment/→ Email finding and verification
  storage/   → SQLite + SQLAlchemy
  utils/     → Logger, encryption, config loader
prompts/     → Plain text AI prompt templates (editable)
config/      → settings.yaml (user config)
```

Full module list with responsibilities is in @ARCHITECTURE.md.

---

## IMPORTANT Rules

**YOU MUST read TASKS.md before writing any code.** Do not implement a module that is already marked complete.

**YOU MUST NOT redesign the architecture.** The system design in ARCHITECTURE.md is the source of truth. Implement within it.

**YOU MUST build UI first.** Every sprint starts with the UI screen. Wire to backend second. See TASKS.md for sprint order.

**YOU MUST keep modules small and single-responsibility.** One file = one concern. No god modules.

**YOU MUST use dependency injection.** Pass dependencies into classes/functions rather than importing globals.

**YOU MUST write to TASKS.md after completing any module.** Mark it [x] immediately.

**NEVER store credentials in plaintext.** All API keys and LinkedIn credentials use utils/encryption.py (Fernet). Store in config/.secrets — never in settings.yaml or .env committed to git.

**NEVER hardcode topics, hashtags, or prompts in Python code.** Topics come from settings.yaml. Prompts come from prompts/*.txt files loaded by ai/prompt_loader.py.

**NEVER run more than 3 worker threads.** worker_pool.py cap is 3. LinkedIn detection risk increases with concurrency.

**NEVER exceed daily budget limits.** budget_tracker.py must be checked before every automation action. If budget is exhausted → skip, do not override.

---

## Code Patterns

**Engine state** is always accessed through core/state_manager.py. Never read/write engine state directly.

**All automation actions** go through core/pipeline.py. Never call interaction_engine.py directly from API routes.

**WebSocket updates** go through api/websocket.py hub. Never push to frontend from deep modules.

**Logging** uses utils/logger.py. Every module gets its own named logger: `logger = get_logger(__name__)`.

**Database sessions** use context managers from storage/database.py. Never leave sessions open.

**Retry logic**: automation actions retry once on failure, then log as FAILED. AI calls retry twice with exponential backoff.

---

## Phase Reminder

We are in **Phase 1 — Local Python App**. Do NOT build:
- Chrome Extension files (manifest.json, content scripts, service workers)
- Any cloud infrastructure
- Any external server dependencies

Phase 2 (Chrome Extension) begins only after Milestone 7 is reached. See TASKS.md.
