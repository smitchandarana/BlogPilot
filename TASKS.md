# Tasks — LinkedIn AI Growth Engine

Status: [ ] = not started, [~] = in progress, [x] = complete

**Before every session:**
1. Read CONTEXT.md (compressed reference — not ARCHITECTURE.md)
2. Read BUILD_PROMPTS.md — copy the exact prompt for your current sprint/session
3. Check this file to see what's [x] done and what's next

Update this file immediately when any module is completed.
Do NOT implement a module already marked [x].

---

## Current Focus

**SPRINT 2 — UI All Screens**
→ See BUILD_PROMPTS.md Sessions 2A through 2D for exact prompts

---

## Sprint 1 — Project Foundation ✅
> **BUILD_PROMPTS.md:** Sessions 1A → 1B → 1C → 1D → 1E (in order)
> **Model:** Sonnet 4.6 (sessions 1A, 1C, 1D, 1E) · Haiku 4.5 (session 1B)

### Backend Scaffold
- [x] backend/main.py — FastAPI app boot, CORS, router registration
- [x] requirements.txt — all dependencies (loose version pins for Python 3.14 compat)
- [x] backend/api/engine.py — start/stop/pause/resume/status endpoints
- [x] backend/api/config.py — topics, settings, prompts CRUD
- [x] backend/api/analytics.py — stats, logs endpoints
- [x] backend/api/campaigns.py — campaign CRUD
- [x] backend/api/leads.py — lead table + enrich trigger
- [x] backend/api/websocket.py — WebSocket hub, event broadcaster

### Core Utils
- [x] backend/utils/logger.py — structured logger, get_logger(name)
- [x] backend/utils/encryption.py — Fernet encrypt/decrypt for credentials
- [x] backend/utils/config_loader.py — YAML loader with file-watch hot-reload
- [x] backend/utils/lock_file.py — single instance enforcement

### Storage Layer
- [x] backend/storage/database.py — SQLite engine, session factory, init_db()
- [x] backend/storage/models.py — all SQLAlchemy ORM models (all 7 tables)
- [x] backend/storage/post_state.py — seen/scored/acted/skipped helpers
- [x] backend/storage/engagement_log.py — write_action(), get_recent()
- [x] backend/storage/budget_tracker.py — check(), increment(), midnight reset
- [x] backend/storage/leads_store.py — create_lead(), update_email(), get_all()

### Frontend Scaffold
- [x] ui/package.json — React + Vite + Tailwind + Recharts + axios
- [x] ui/src/App.jsx — router shell, nav, all 10 page routes
- [x] ui/src/api/client.js — axios base client for localhost:8000
- [x] ui/src/hooks/useWebSocket.js — WS connection, reconnect, event dispatch
- [x] ui/src/hooks/useEngine.js — engine state, start/stop/pause/resume
- [x] ui/src/components/Layout.jsx — sidebar nav + main content area

---

## Sprint 2 — UI All Screens (Static / Mock Data)
> **BUILD_PROMPTS.md:** Sessions 2A → 2B → 2C → 2D → Sprint 2 Review
> **Model:** Sonnet 4.6 (all sessions) · Opus 4.6 (review only) · Run /clear before starting

- [x] ui/src/pages/Dashboard.jsx — status, counters, budget bars, activity feed
- [x] ui/src/pages/EngineControl.jsx — toggles, activity window, day selector
- [x] ui/src/pages/Topics.jsx — topic tags, hashtags, blacklist, score threshold
- [x] ui/src/pages/FeedEngagement.jsx — mode selector, comment log, interval
- [x] ui/src/pages/ContentStudio.jsx — post generator, scheduler, post queue
- [x] ui/src/pages/Campaigns.jsx — campaign list + builder UI
- [x] ui/src/pages/Leads.jsx — lead table, email status, CSV export
- [x] ui/src/pages/Analytics.jsx — charts (7d/30d), top topics, funnel
- [x] ui/src/pages/PromptEditor.jsx — prompt list, editor, test panel
- [x] ui/src/pages/Settings.jsx — API keys, limits, browser profile, danger zone
- [x] ui/src/components/EngineToggle.jsx — big start/stop/pause button
- [x] ui/src/components/BudgetBar.jsx — per-action progress bar
- [x] ui/src/components/ActivityFeed.jsx — live scrolling log
- [x] ui/src/components/LeadTable.jsx — sortable/filterable table (built into Leads.jsx)
- [x] ui/src/components/CampaignBuilder.jsx — step drag-and-drop builder
- [x] ui/src/components/PromptTestPanel.jsx — paste post, see AI output

---

## Sprint 3 — Core Engine
> **BUILD_PROMPTS.md:** Sessions 3A → 3B → 3C
> **Model:** opusplan alias for ALL sessions · Run /clear before starting

- [x] backend/core/state_manager.py — engine state FSM, transitions, getters
- [x] backend/core/task_queue.py — queue.Queue wrapper, priority support
- [x] backend/core/worker_pool.py — ThreadPoolExecutor max=3, submit(), drain()
- [x] backend/core/scheduler.py — APScheduler setup, SQLite job store
- [x] backend/core/rate_limiter.py — per-action hourly cap checks
- [x] backend/core/circuit_breaker.py — error rate monitor, auto-pause trigger
- [x] backend/core/engine.py — master engine class, wires all core modules
- [x] backend/core/pipeline.py — full post processing pipeline (stub)
- [x] Wire start/stop/pause/resume API → engine via state_manager
- [x] Wire engine state → WebSocket → Dashboard UI
- [ ] Wire budget tracker → BudgetBar component via WebSocket

**Milestone 2 check:** Start/stop/pause/resume work. WebSocket shows live state. Scheduler fires tasks. Queue and workers visible in logs.

---

## Sprint 4 — Browser Automation ✅
> **BUILD_PROMPTS.md:** Sessions 4A → 4B → 4C → 4D
> **Model:** opusplan (4A, 4C, 4D) · Sonnet 4.6 (4B) · Run /clear before starting

- [x] backend/automation/browser.py — Playwright launch, stealth, persistent profile
- [x] backend/automation/linkedin_login.py — login, cookie save/load, re-auth detect
- [x] backend/automation/feed_scanner.py — scroll feed, extract post DOM elements
- [x] backend/automation/profile_scraper.py — visit profile, extract all fields
- [x] backend/automation/interaction_engine.py — like, comment, connect, follow
- [x] backend/automation/human_behavior.py — random_delay(), type_slowly(), scroll()
- [x] backend/automation/post_publisher.py — navigate to post composer, type, submit
- [x] backend/core/pipeline.py — full 10-step pipeline (AI/strategy stubs for Sprint 5/7)
- [x] CAPTCHA detection → circuit_breaker → auto-pause → alert WebSocket event
- [x] backend/utils/setup_credentials.py — one-time credential encryption helper
- [x] tests/test_feed_scanner.py — unit tests with mock page objects

**Milestone 3 check:** Engine opens browser, logs into LinkedIn, reads at least 10 posts, posts appear in Feed log in UI.

---

## Sprint 5 — AI Layer
> **BUILD_PROMPTS.md:** Sessions 5A → 5B
> **Model:** Sonnet 4.6 · Run /clear before starting

- [x] backend/ai/groq_client.py — Groq API wrapper, retry x2, exponential backoff
- [x] backend/ai/prompt_loader.py — load from prompts/*.txt, hot-reload on change
- [x] backend/ai/relevance_classifier.py — call Groq, return score + reasoning
- [x] backend/ai/comment_generator.py — call Groq, return comment text
- [x] backend/ai/post_generator.py — topic + style → LinkedIn post
- [x] backend/ai/note_writer.py — profile data → connection request note
- [x] backend/ai/reply_generator.py — thread context → reply text
- [x] Wire Prompt Editor UI → settings API → prompt_loader (api/config.py already wired)
- [x] Wire PromptTestPanel → POST /api/config/prompts/test endpoint (fixed secrets reading)
- [x] Wire post_generator → ContentStudio Generate button (ContentStudio already calls testPrompt)

**Milestone 4 check:** Post → Groq classifier → score → Groq comment → text. Full pipeline logs in UI. Prompt editor changes affect output live.

---

## Sprint 6 — Email Enrichment
> **BUILD_PROMPTS.md:** Session 6 (single session)
> **Model:** Sonnet 4.6 · Run /clear before starting

- [ ] backend/enrichment/email_enricher.py — orchestrate all methods, return result
- [ ] backend/enrichment/dom_email_scraper.py — read email from 1st degree profile DOM
- [ ] backend/enrichment/pattern_generator.py — generate [f.last@domain, first@domain, ...]
- [ ] backend/enrichment/smtp_verifier.py — MX lookup + SMTP handshake
- [ ] backend/enrichment/hunter_client.py — Hunter.io API (optional, key-gated)
- [ ] Wire Leads page → GET /api/leads endpoint
- [ ] Wire Enrich button → POST /api/leads/{id}/enrich endpoint
- [ ] Wire Bulk Enrich → POST /api/leads/enrich-all endpoint
- [ ] Wire CSV Export → GET /api/leads/export endpoint

**Milestone 6 check:** Profile visited → email found → lead in DB → appears in Leads UI → CSV export includes email.

---

## Sprint 7 — Campaigns + Growth Intelligence
> **BUILD_PROMPTS.md:** Sessions 7A → 7B
> **Model:** Sonnet 4.6 (7A) · opusplan (7B) · Run /clear before starting

- [ ] backend/growth/viral_detector.py — calculate engagement velocity, set priority
- [ ] backend/growth/influencer_monitor.py — poll watchlist profiles for new posts
- [ ] backend/growth/engagement_strategy.py — decide action type from score + budget
- [ ] backend/growth/campaign_engine.py — step FSM, next_action_at logic, executor
- [ ] Wire Campaigns UI → full CRUD via /api/campaigns
- [ ] Wire campaign enrollment → leads → campaign_enrollments table
- [ ] Wire post_publisher → ContentStudio scheduler queue
- [ ] Wire post schedule queue → APScheduler

---

## Sprint 8 — Analytics + Polish
> **BUILD_PROMPTS.md:** Sessions 8A → 8B → 8C
> **Model:** Sonnet 4.6 (8A, 8C) · Opus 4.6 (8B review) · Run /clear before starting

- [ ] backend/api/analytics.py — full stats queries (daily, weekly, by topic)
- [ ] Wire Analytics page charts → real DB data
- [ ] Wire Dashboard counters → real budget_tracker data
- [ ] Wire ActivityFeed → WebSocket activity events (real actions)
- [ ] Wire alert system → WebSocket alert events → Dashboard banner
- [ ] Add weekly summary generator (AI summarise week's engagement)
- [ ] End-to-end test: engine runs 30 minutes, no crashes, no duplicates
- [ ] README.md — setup guide, how to run, config instructions

**Milestone 7 check:** Engine runs 4 hours unattended. Hits daily budget, auto-pauses, resumes next day. All logs clean. Analytics show real data.

---

## Phase 2 — Chrome Extension (DO NOT START until Milestone 7)

- [ ] Create /extension directory
- [ ] manifest.json — Manifest V3
- [ ] background/service_worker.js
- [ ] content_scripts/feed_scanner.js
- [ ] content_scripts/interaction_engine.js
- [ ] content_scripts/human_behavior.js
- [ ] content_scripts/profile_scraper.js
- [ ] popup/popup.html + popup.js
- [ ] options/dashboard.html (port React UI)
- [ ] Migrate SQLite → chrome.storage.local
- [ ] Migrate APScheduler → chrome.alarms
- [ ] Publish to Chrome Web Store

---

## Milestone Checklist

- [x] M1 — UI Shell: all 10 pages navigate, settings saves, no broken routes
- [ ] M2 — Engine Controls: start/stop/pause/resume work, WebSocket live state
- [ ] M3 — LinkedIn Feed Reads: 10+ posts extracted, appear in UI log
- [ ] M4 — AI Pipeline End-to-End: post → score → comment text in UI
- [ ] M5 — First Real Comment Posted on LinkedIn
- [ ] M6 — Email Enrichment: first email found, in Leads table, in CSV export
- [ ] M7 — Runs 4 Hours Unattended: budget auto-pause, clean logs, real analytics
- [ ] M8 — Phase 2 Ready: Chrome Extension conversion begins
