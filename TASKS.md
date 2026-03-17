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

**All Sprints 1–8 COMPLETE. Self-Learning Engine COMPLETE. Content Intelligence (Phase A + B + B2) COMPLETE.** Phase 1 development is finished.
→ Remaining: M7 runtime validation (4-hour unattended run) — use `python scripts/m7_validate.py` to check criteria
→ Phase 2 (Chrome Extension) begins after M7 is validated.

### Post-Sprint Enhancement: Content Intelligence + Structured Post Generation ✅
Extracts structured insights from research snippets, aggregates patterns, and enables grounded LinkedIn post generation with real signal inputs.

- [x] `backend/storage/models.py` — added `ContentInsight` and `ContentPattern` ORM models
- [x] `backend/storage/database.py` — migration for `processed_for_insights` column on `research_snippets`
- [x] `prompts/content_extractor.txt` — AI extraction prompt (subtopic, pain_point, hook_type, content_style, key_insight, audience_segment, sentiment, specificity_score)
- [x] `prompts/structured_post.txt` — structured post generation prompt with evidence injection + anti-slop rules
- [x] `backend/ai/prompt_loader.py` — registered `content_extractor` and `structured_post` prompts
- [x] `backend/research/content_extractor.py` — NEW: batch-processes unprocessed snippets → `ContentInsight` rows via Groq (semaphore=2)
- [x] `backend/research/pattern_aggregator.py` — NEW: SQL GROUP BY aggregation of insights → `ContentPattern` rows; evidence block generation
- [x] `backend/api/intelligence.py` — NEW: `/intelligence` router (insights, patterns, patterns/for-generation, extract, status)
- [x] `backend/main.py` — registered intelligence router at `/intelligence` prefix
- [x] `backend/ai/post_generator.py` — added `generate_structured()` alongside `generate()` (same return shape, backward compatible)
- [x] `backend/api/content.py` — added `POST /content/generate-structured` endpoint
- [x] `config/settings.yaml` — added `content_intelligence:` config block
- [x] `backend/core/scheduler.py` — added `_job_content_extraction` job (every 4h ±20min jitter)
- [x] `ui/src/api/client.js` — added `intelligence` export + `generateStructured` to content export
- [x] `ui/src/pages/ContentStudio.jsx` — mode toggle (Quick/Structured), IntelligencePanel (click-to-fill), structured form (subtopic, audience, pain_point, hook_intent, belief_to_challenge, core_insight, proof_type)
- [x] `backend/storage/models.py` — added `GenerationSession` model (Phase B)
- [x] `backend/storage/database.py` — migration to create `generation_sessions` table
- [x] `backend/api/intelligence.py` — added `POST /intelligence/extract-text`, `POST /intelligence/session`, `GET /intelligence/preferences` endpoints
- [x] `backend/learning/content_preference_learner.py` — NEW: mines GenerationSession history for best hook types, audiences, styles; returns defaults for auto-fill
- [x] `ui/src/api/client.js` — added `extractText`, `logSession`, `preferences` to intelligence export
- [x] `ui/src/pages/ContentStudio.jsx` — Phase B: auto-fill structured form from learned preferences; "Learn from Content" paste panel with Extract & Learn; session tracking (logSession on generate, publish, schedule)
- [x] `ui/src/pages/Dashboard.jsx` — intelligence status widget: total insights, total patterns, unprocessed snippets count, last extraction date
- [x] `backend/api/intelligence.py` — added `GET /intelligence/patterns/{pattern_id}` endpoint (pattern + supporting insights for drilldown)
- [x] `ui/src/api/client.js` — added `patternDetail(id)` to intelligence export
- [x] `backend/learning/content_preference_learner.py` — added `top_posts` (top 3 published sessions by quality score) to preferences response
- [x] `backend/ai/post_generator.py` — `generate_structured()` accepts `style_examples` list; injects as `{style_reference}` block in prompt when provided
- [x] `prompts/structured_post.txt` — added `{style_reference}` placeholder at end of prompt
- [x] `backend/api/content.py` — `StructuredGenerateRequest` accepts `style_examples`; passes through to `generate_structured()`
- [x] `ui/src/pages/ContentStudio.jsx` — InsightDrilldownModal (click ✦ on any pattern → modal showing supporting insights + "Use this insight" fill-all); "Write like my best posts" button (injects top published sessions as style reference into next generate call)
- [x] `scripts/m7_validate.py` — NEW: M7 runtime validation script (9 checks: DB, actions today, budget enforcement, midnight reset, feed scan activity, circuit breaker, error rate, analytics queries, content intelligence)

### Post-Sprint Enhancement: Comment Approval Queue ✅
Human-in-the-loop approval flow for AI-generated comments. Comments are held in PREVIEW state until approved or rejected via Dashboard.

- [x] `backend/core/pipeline.py` — `run_approve_comment(post_id, comment_text)` sync entry point + `_async_approve_comment()`: opens browser, posts approved comment, updates state ACTED/FAILED, logs quality + budgets
- [x] `backend/api/engine.py` — `GET /engine/pending-previews` (returns PREVIEW posts), `POST /engine/approve-comment` (queues to worker pool), `POST /engine/reject-comment` (marks SKIPPED, no browser)
- [x] `ui/src/components/PreviewQueue.jsx` — NEW: Dashboard panel showing pending comments; editable AI comment, Approve/Reject buttons, live via WebSocket `post_preview` events
- [x] `ui/src/pages/Dashboard.jsx` — added `<PreviewQueue />` between engine toggle and stats grid
- [x] `ui/src/api/client.js` — `pendingPreviews()`, `approveComment()`, `rejectComment()` added to engine export

### Post-Sprint Fix: Lock File Reliability ✅
- [x] `backend/utils/lock_file.py` — Fixed `msvcrt.locking` position bug on Windows (`seek(0)` before `LK_UNLCK`); added stale-lock auto-cleanup on startup (checks if PID in lock file is alive, removes if dead)

### Post-Sprint Enhancement: Specific Subtopic Extraction
- [x] AI-powered subtopic extraction from research snippets (replaces broad topic matching)
- [x] `prompts/topic_extractor.txt` — new prompt for extracting specific subtopics
- [x] `backend/ai/prompt_loader.py` — registered topic_extractor prompt
- [x] `backend/storage/models.py` — added `domain` column to ResearchedTopic
- [x] `backend/storage/database.py` — migration for existing DBs
- [x] `backend/research/topic_researcher.py` — refactored pipeline: domain-filter → AI extract → dedup → score → quality gate → store
- [x] `backend/api/research.py` — DELETE /research/topics (clear all) endpoint
- [x] `ui/src/api/client.js` — clearAll method added to research API
- [x] `ui/src/pages/ContentStudio.jsx` — domain badge on topic cards + "Clear All" button
- [x] `config/settings.yaml` — max_subtopics_per_domain, max_total_subtopics, min_subtopic_score

### Post-Sprint Enhancement: Self-Learning Engine ✅
6 self-learning capabilities: comment quality learning, topic targeting, scoring calibration, timing optimization, random scan intervals, hashtag/topic search scanning.

#### Phase A — Wire Existing Scaffolding
- [x] `backend/core/pipeline.py` — wire quality logging after comment post, topic matching via `_match_topic()`, pass `topic_tag` to actions, call `topic_rotator.record_engagement()`
- [x] `backend/automation/interaction_engine.py` — add `topic_tag` param to `like_post()`, `comment_post()`, thread through to `engagement_log.write_action()`
- [x] `backend/api/content.py` — wire `quality_log.log_post()` after successful post publish

#### Phase B — Scheduler Randomization + Hashtag Scanning
- [x] `backend/core/scheduler.py` — add APScheduler `jitter` to all interval jobs (feed_scan ±300s, campaign ±180s, rotation ±1800s, research ±600s)
- [x] `backend/automation/hashtag_scanner.py` — NEW: scan LinkedIn hashtag feeds + content search results, random subset per session
- [x] `backend/core/pipeline.py` — integrate hashtag/search scanning after home feed scan (config-gated)

#### Phase C — Learning Feedback Loops
- [x] `backend/learning/__init__.py` — NEW: learning package init
- [x] `backend/learning/comment_monitor.py` — NEW: scheduler job revisits posts, checks if our comment got a reply, updates CommentQualityLog
- [x] `backend/learning/scoring_calibrator.py` — NEW: groups posts by score bucket, calculates engagement/reply rates, recommends optimal_min_score
- [x] `backend/learning/timing_analyzer.py` — NEW: groups actions by hour/day, finds best engagement windows, returns recommendations
- [x] `backend/api/analytics.py` — 4 new learning endpoints: comment-quality, post-quality, scoring-calibration, timing
- [x] `backend/core/scheduler.py` — register comment_monitor job (every 4h ±600s)

#### Phase D — Auto-Tuning + UI
- [x] `backend/learning/auto_tuner.py` — NEW: auto-adjusts `min_relevance_score` (±0.5/cycle, bounded 4.0-9.0, requires 50+ posts) + narrows activity hours
- [x] `backend/ai/comment_generator.py` — enriches prompts with best-performing angle from engagement data
- [x] `backend/core/scheduler.py` — register auto_tune job (every 24h ±3600s)
- [x] `backend/core/engine.py` — call `auto_tuner.tune_if_stale(db)` on engine start
- [x] `ui/src/pages/Analytics.jsx` — Learning Insights section: comment quality stats, score calibration bars, timing heatmap, angle distribution
- [x] `ui/src/api/client.js` — 4 learning API methods added to analytics export
- [x] `config/settings.yaml` — full `learning:` config block + hashtag/search scanning + jitter settings

---

## Sprint 1 — Project Foundation ✅
> **BUILD_PROMPTS.md:** Sessions 1A → 1B → 1C → 1D → 1E (in order)
> **Model:** Sonnet 4.6 (sessions 1A, 1C, 1D, 1E) · Haiku 4.5 (session 1B)

### Backend Scaffold
- [x] backend/main.py — FastAPI app boot, CORS, router registration (8 routers: engine, config, analytics, campaigns, leads, content, websocket, server)
- [x] requirements.txt — all dependencies (loose version pins for Python 3.14 compat)
- [x] backend/api/engine.py — start/stop/pause/resume/status endpoints
- [x] backend/api/config.py — topics, settings, prompts CRUD + API key management (GET/POST /api-keys/groq)
- [x] backend/api/analytics.py — stats, logs endpoints
- [x] backend/api/campaigns.py — campaign CRUD
- [x] backend/api/leads.py — lead table + enrich trigger
- [x] backend/api/websocket.py — WebSocket hub, event broadcaster

### Core Utils
- [x] backend/utils/logger.py — structured logger, get_logger(name)
- [x] backend/utils/encryption.py — Fernet encrypt/decrypt for credentials (PBKDF2 + random salt)
- [x] backend/utils/config_loader.py — YAML loader with file-watch hot-reload
- [x] backend/utils/lock_file.py — single instance enforcement (msvcrt on Windows)

### Storage Layer
- [x] backend/storage/database.py — SQLite engine, session factory, init_db()
- [x] backend/storage/models.py — all SQLAlchemy ORM models (10 tables: posts, leads, actions_log, campaigns, campaign_enrollments, budget, settings, scheduled_posts, comment_quality_log, post_quality_log, topic_performance)
- [x] backend/storage/post_state.py — seen/scored/acted/skipped helpers
- [x] backend/storage/engagement_log.py — write_action(), get_recent()
- [x] backend/storage/budget_tracker.py — check(), increment(), midnight reset
- [x] backend/storage/leads_store.py — create_lead(), update_email(), get_all()

### Frontend Scaffold
- [x] ui/package.json — React + Vite + Tailwind + Recharts + axios
- [x] ui/src/App.jsx — router shell, nav, all 10 page routes
- [x] ui/src/api/client.js — axios base client for localhost:8000 (7 exports: engine, config, analytics, campaigns, leads, content, server)
- [x] ui/src/hooks/useWebSocket.js — WS connection, reconnect, event dispatch
- [x] ui/src/hooks/useEngine.js — engine state, start/stop/pause/resume
- [x] ui/src/components/Layout.jsx — sidebar nav + main content area

---

## Sprint 2 — UI All Screens (Static / Mock Data) ✅
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
- [x] ui/src/pages/Settings.jsx — API keys (Groq key save/status UI), limits, browser profile, danger zone
- [x] ui/src/components/EngineToggle.jsx — big start/stop/pause button
- [x] ui/src/components/BudgetBar.jsx — per-action progress bar
- [x] ui/src/components/ActivityFeed.jsx — live scrolling log
- [x] ui/src/components/LeadTable.jsx — sortable/filterable table (built into Leads.jsx)
- [x] ui/src/components/CampaignBuilder.jsx — step drag-and-drop builder
- [x] ui/src/components/PromptTestPanel.jsx — paste post, see AI output

---

## Sprint 3 — Core Engine ✅
> **BUILD_PROMPTS.md:** Sessions 3A → 3B → 3C
> **Model:** opusplan alias for ALL sessions · Run /clear before starting

- [x] backend/core/state_manager.py — engine state FSM, transitions, getters
- [x] backend/core/task_queue.py — queue.Queue wrapper, priority support
- [x] backend/core/worker_pool.py — ThreadPoolExecutor max=3, submit(), drain()
- [x] backend/core/scheduler.py — APScheduler setup, SQLite job store (8 jobs: feed_scan, hourly_reset, budget_reset, campaign_processing, post_publishing, topic_rotation, comment_monitor, auto_tune)
- [x] backend/core/rate_limiter.py — per-action hourly cap checks
- [x] backend/core/circuit_breaker.py — error rate monitor, auto-pause trigger + auto-resume timer
- [x] backend/core/engine.py — master engine class, wires all core modules
- [x] backend/core/pipeline.py — full post processing pipeline (10-step pipeline)
- [x] Wire start/stop/pause/resume API → engine via state_manager
- [x] Wire engine state → WebSocket → Dashboard UI
- [x] Wire budget tracker → BudgetBar component via WebSocket

**Milestone 2 check:** Start/stop/pause/resume work. WebSocket shows live state. Scheduler fires tasks. Queue and workers visible in logs.

---

## Sprint 4 — Browser Automation ✅
> **BUILD_PROMPTS.md:** Sessions 4A → 4B → 4C → 4D
> **Model:** opusplan (4A, 4C, 4D) · Sonnet 4.6 (4B) · Run /clear before starting

- [x] backend/automation/browser.py — Playwright launch, stealth, persistent profile
- [x] backend/automation/linkedin_login.py — login, cookie save/load, re-auth detect
- [x] backend/automation/feed_scanner.py — scroll feed, extract post DOM elements
- [x] backend/automation/profile_scraper.py — visit profile, extract all fields
- [x] backend/automation/interaction_engine.py — like, comment, connect, follow, endorse, send_inmail
- [x] backend/automation/human_behavior.py — random_delay(), type_slowly(), scroll()
- [x] backend/automation/post_publisher.py — navigate to post composer, type, submit
- [x] backend/core/pipeline.py — full 10-step pipeline (AI/strategy stubs for Sprint 5/7)
- [x] CAPTCHA detection → circuit_breaker → auto-pause → alert WebSocket event
- [x] backend/utils/setup_credentials.py — one-time credential encryption helper
- [x] tests/test_feed_scanner.py — unit tests with mock page objects

**Milestone 3 check:** Engine opens browser, logs into LinkedIn, reads at least 10 posts, posts appear in Feed log in UI.

---

## Sprint 5 — AI Layer ✅
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

## Sprint 6 — Email Enrichment ✅
> **BUILD_PROMPTS.md:** Session 6 (single session)
> **Model:** Sonnet 4.6 · Run /clear before starting

- [x] backend/enrichment/email_enricher.py — orchestrate all methods, return result
- [x] backend/enrichment/dom_email_scraper.py — read email from 1st degree profile DOM
- [x] backend/enrichment/pattern_generator.py — generate [f.last@domain, first@domain, ...]
- [x] backend/enrichment/smtp_verifier.py — MX lookup + SMTP handshake
- [x] backend/enrichment/hunter_client.py — Hunter.io API (optional, key-gated)
- [x] Wire Leads page → GET /api/leads endpoint
- [x] Wire Enrich button → POST /api/leads/{id}/enrich endpoint
- [x] Wire Bulk Enrich → POST /api/leads/enrich-all endpoint
- [x] Wire CSV Export → GET /api/leads/export endpoint

**Milestone 6 check:** Profile visited → email found → lead in DB → appears in Leads UI → CSV export includes email.

---

## Sprint 7 — Campaigns + Growth Intelligence ✅
> **BUILD_PROMPTS.md:** Sessions 7A → 7B
> **Model:** Sonnet 4.6 (7A) · opusplan (7B) · Run /clear before starting

- [x] backend/growth/viral_detector.py — calculate engagement velocity, set priority
- [x] backend/growth/influencer_monitor.py — poll watchlist profiles for new posts
- [x] backend/growth/engagement_strategy.py — decide action type from score + budget
- [x] backend/growth/campaign_engine.py — step FSM, next_action_at logic, executor
- [x] backend/growth/topic_rotator.py — auto-rotation of topics based on engagement performance (24h cycle)
- [x] Wire Campaigns UI → full CRUD via /api/campaigns (CRUD already wired; enrollment fixed with next_action_at)
- [x] Wire campaign enrollment → leads → campaign_enrollments table
- [x] Wire post_publisher → ContentStudio scheduler queue (backend/api/content.py — schedule, publish-now, queue endpoints + ScheduledPost model)
- [x] Wire post schedule queue → APScheduler (_job_post_publishing fires every 1 min, submits due posts to worker pool)
- [x] Wire topic rotation → APScheduler (_job_topic_rotation fires every 24h, demotes underperformers, promotes fresh topics)

---

## Sprint 8 — Analytics + Polish + Security ✅
> **BUILD_PROMPTS.md:** Sessions 8A → 8B → 8C
> **Model:** Sonnet 4.6 (8A, 8C) · Opus 4.6 (8B review) · Run /clear before starting

### Analytics Wiring
- [x] backend/api/analytics.py — full stats queries (daily, weekly, by topic, campaign funnel, skipped/acted posts, comment history)
- [x] Wire Analytics page charts → real DB data (removed all hardcoded mock data)
- [x] Wire Dashboard counters → real budget_tracker data (budget_used in engine status + WebSocket budget_update)
- [x] Wire ActivityFeed → WebSocket activity events (real actions) — already wired in Sprint 3
- [x] Wire alert system → WebSocket alert events → Dashboard banner + circuit breaker reset button
- [x] Add weekly summary generator (real stats-based text summary from DB)
- [x] Wire FeedEngagement page → real data (acted posts, skipped posts, comment history from DB)
- [x] Wire Topics page → full persistence (hashtags, blacklist, industries, watchlists saved to YAML)
- [x] Fix settings persistence — PUT /settings now writes back to config/settings.yaml

### Security Hardening
- [x] Security: PBKDF2 + random salt encryption (replaced weak hostname-based key derivation)
- [x] Security: msvcrt lock file on Windows (replaced TOCTOU race condition)
- [x] Security: File permission hardening (chmod 600 on secrets files)
- [x] Security: Restricted CORS methods + prompt size validation

### Additional Features
- [x] backend/api/server.py — server restart (os.execv) + shutdown (os._exit) + info endpoints
- [x] backend/api/config.py — Groq API key management (GET/POST /api-keys/groq with masked key display)
- [x] Settings UI — Groq API key status indicator, save key input, masked key display
- [x] Add send_inmail method to interaction engine
- [x] Add circuit breaker manual reset endpoint + Dashboard UI button
- [x] backend/storage/quality_log.py — AI comment/post quality metrics tracking (reply rates, angles, approval rates)
- [x] backend/utils/paths.py — dev vs PyInstaller frozen mode path resolution

### Testing
- [x] End-to-end pipeline test (test_e2e.py — pipeline flow, budget exhaustion)
- [x] Budget safety tests (check/increment/reset/unlimited)
- [x] Campaign execution tests (test_campaigns.py — enrollment, step advancement, completion)
- [x] run_tests.py — master test runner with config checks, credential validation, full suite
- [x] All 94 tests passing (test_utils, test_storage, test_ai_client, test_campaigns, test_e2e, test_enrichment, test_feed_scanner, test_research)

### Packaging & Distribution
- [x] launcher.py — single entry point for dev and EXE modes (auto-opens browser)
- [x] blogpilot.spec — PyInstaller config for single-file EXE build
- [x] GUIDE.md — user setup guide (EXE + source modes)

### Documentation
- [x] README.md — developer setup guide, how to run, config instructions

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
- [x] M2 — Engine Controls: start/stop/pause/resume work, WebSocket live state
- [x] M3 — LinkedIn Feed Reads: 10+ posts extracted, appear in UI log
- [x] M4 — AI Pipeline End-to-End: post → score → comment text in UI
- [x] M5 — First Real Comment Posted on LinkedIn
- [x] M6 — Email Enrichment: first email found, in Leads table, in CSV export
- [~] M7 — Runs 4 Hours Unattended: all code complete, analytics wired, needs runtime validation run
- [ ] M8 — Phase 2 Ready: Chrome Extension conversion begins

---

## Test Suite Summary (94/94 passing)

| Suite | Tests | Status |
|---|---|---|
| test_utils.py | 4 | ✅ |
| test_storage.py | 8 | ✅ |
| test_ai_client.py | 5 | ✅ |
| test_campaigns.py | 7 | ✅ |
| test_e2e.py | 10 | ✅ |
| test_enrichment.py | 11 | ✅ |
| test_feed_scanner.py | 10 | ✅ |
| test_research.py | 29 | ✅ |
| **Total** | **94** | **✅ All passing** |

---

## Known Issues

All previously known issues have been resolved:
- ~~Server restart API (os.execv)~~ — Fixed: now uses `subprocess.Popen` + `os._exit` instead of `os.execv`
- ~~Profile scraper selectors~~ — Fixed: expanded fallback selectors for name, title, company, degree
- ~~Lock file cleanup on Windows~~ — Fixed: skip file deletion on Windows, suppress log-during-teardown noise
- ~~Lock file stale on crash/os._exit~~ — Fixed: `seek(0)` before `LK_UNLCK` + auto-cleanup of dead-PID locks on startup
