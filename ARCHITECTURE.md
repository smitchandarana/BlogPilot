# Architecture — LinkedIn AI Growth Engine

## System Overview

Local Python application. React UI on localhost:3000. FastAPI backend on localhost:8000. Playwright controls a real browser session with a persistent LinkedIn profile. Groq handles all AI inference. SQLite stores everything locally. No cloud dependencies.

---

## Layer Map

```
┌─────────────────────────────────────────────────────────────┐
│  UI LAYER — React + Vite + Tailwind (localhost:3000)        │
│  Dashboard · Control · Topics · Feed · Content · Campaigns  │
│  Leads · Analytics · Prompts · Settings                     │
└────────────────────┬────────────────────────────────────────┘
                     │ REST + WebSocket
┌────────────────────▼────────────────────────────────────────┐
│  API LAYER — FastAPI (localhost:8000)                        │
│  api/engine.py · api/config.py · api/analytics.py           │
│  api/campaigns.py · api/leads.py · api/websocket.py         │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│  CORE ENGINE — Background Worker Runtime                     │
│  core/engine.py        — master engine, state machine       │
│  core/scheduler.py     — APScheduler, cron/interval jobs    │
│  core/task_queue.py    — queue.Queue, FIFO + priority       │
│  core/worker_pool.py   — ThreadPoolExecutor (max 3)         │
│  core/rate_limiter.py  — per-action hourly caps             │
│  core/state_manager.py — RUNNING/PAUSED/STOPPED/ERROR      │
│  core/pipeline.py      — orchestrates full scan→act flow    │
│  core/circuit_breaker.py — auto-pause on error spike       │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│  AUTOMATION LAYER — Playwright                               │
│  automation/browser.py          — instance, stealth, profile│
│  automation/linkedin_login.py   — auth, cookies, re-auth    │
│  automation/feed_scanner.py     — DOM extraction, scroll    │
│  automation/profile_scraper.py  — name, title, co., email   │
│  automation/interaction_engine.py — like, comment, connect  │
│  automation/human_behavior.py   — delays, typing, scroll    │
│  automation/post_publisher.py   — publishes generated posts │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│  AI LAYER — Groq API                                        │
│  ai/groq_client.py           — wrapper, retry, rate limit   │
│  ai/prompt_loader.py         — loads from prompts/*.txt     │
│  ai/relevance_classifier.py  — score post 0-10             │
│  ai/comment_generator.py     — contextual comment          │
│  ai/post_generator.py        — original LinkedIn posts      │
│  ai/note_writer.py           — connection request note      │
│  ai/reply_generator.py       — comment thread replies       │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│  GROWTH LAYER                                                │
│  growth/viral_detector.py      — engagement velocity        │
│  growth/influencer_monitor.py  — watch specific accounts    │
│  growth/engagement_strategy.py — decide action per post     │
│  growth/campaign_engine.py     — multi-step sequence FSM    │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│  ENRICHMENT LAYER                                            │
│  enrichment/email_enricher.py    — orchestrates all methods │
│  enrichment/dom_email_scraper.py — 1st degree DOM read      │
│  enrichment/pattern_generator.py — name+domain patterns     │
│  enrichment/smtp_verifier.py     — verify without sending   │
│  enrichment/hunter_client.py     — optional Hunter.io API   │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│  STORAGE LAYER — SQLite + SQLAlchemy                        │
│  storage/database.py      — connection manager, migrations  │
│  storage/models.py        — ORM models (all tables)         │
│  storage/post_state.py    — deduplication tracker           │
│  storage/engagement_log.py — action history writer          │
│  storage/budget_tracker.py — daily counters, midnight reset │
│  storage/leads_store.py   — lead CRUD                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### posts
| Column | Type | Description |
|---|---|---|
| id | TEXT PK | SHA256 of LinkedIn post URL |
| url | TEXT | Full LinkedIn post URL |
| author_name | TEXT | Display name of author |
| author_url | TEXT | LinkedIn profile URL of author |
| text | TEXT | Full post text content |
| like_count | INT | Likes at time of scan |
| comment_count | INT | Comments at time of scan |
| relevance_score | FLOAT | AI score 0-10 |
| state | TEXT | SEEN / SCORED / ACTED / SKIPPED / FAILED |
| action_taken | TEXT | LIKE / COMMENT / CONNECT / NONE |
| comment_text | TEXT | AI generated comment if posted |
| scanned_at | DATETIME | When first seen |
| acted_at | DATETIME | When action was taken |

### leads
| Column | Type | Description |
|---|---|---|
| id | TEXT PK | UUID |
| linkedin_url | TEXT UNIQUE | Profile URL |
| first_name | TEXT | |
| last_name | TEXT | |
| title | TEXT | Job title |
| company | TEXT | Company name |
| company_domain | TEXT | e.g. tcs.com |
| email | TEXT | Found email address |
| email_status | TEXT | NOT_FOUND / FOUND / VERIFIED / BOUNCED |
| email_method | TEXT | DOM / PATTERN / SMTP / HUNTER |
| connection_degree | INT | 1 / 2 / 3 |
| source_post_id | TEXT FK | Post that led to this profile |
| campaign_id | TEXT FK | If enrolled in campaign |
| status | TEXT | NEW / CONTACTED / REPLIED / CONVERTED |
| created_at | DATETIME | |

### actions_log
| Column | Type | Description |
|---|---|---|
| id | TEXT PK | UUID |
| action_type | TEXT | LIKE / COMMENT / CONNECT / FOLLOW / VISIT / MESSAGE |
| target_url | TEXT | Post or profile URL |
| target_name | TEXT | Author or profile name |
| result | TEXT | SUCCESS / FAILED / SKIPPED |
| comment_text | TEXT | If action was COMMENT |
| error_msg | TEXT | If result was FAILED |
| timestamp | DATETIME | When action was executed |

### campaigns
| Column | Type | Description |
|---|---|---|
| id | TEXT PK | UUID |
| name | TEXT | Campaign name |
| steps | JSON | Array of step definitions |
| status | TEXT | ACTIVE / PAUSED / COMPLETED |
| created_at | DATETIME | |

### campaign_enrollments
| Column | Type | Description |
|---|---|---|
| id | TEXT PK | UUID |
| campaign_id | TEXT FK | |
| lead_id | TEXT FK | |
| current_step | INT | Which step they're on (0-indexed) |
| next_action_at | DATETIME | When to execute next step |
| status | TEXT | IN_PROGRESS / COMPLETED / FAILED |

### budget
| Column | Type | Description |
|---|---|---|
| action_type | TEXT PK | LIKE / COMMENT / CONNECT / VISIT / MESSAGE / POST |
| count_today | INT | Actions taken today |
| limit_per_day | INT | Configured daily max |
| reset_at | DATETIME | Next midnight reset |

### settings
| Column | Type | Description |
|---|---|---|
| key | TEXT PK | Setting key |
| value | TEXT | JSON-encoded value |
| updated_at | DATETIME | |

---

## Engine State Machine

```
STOPPED ──start()──▶ RUNNING
RUNNING ──pause()──▶ PAUSED
PAUSED ──resume()──▶ RUNNING
RUNNING ──stop()───▶ STOPPED
PAUSED ──stop()────▶ STOPPED
RUNNING ──error────▶ ERROR
ERROR ──recover()──▶ STOPPED
```

All state transitions go through `core/state_manager.py`. API routes call state_manager methods. UI reads state via WebSocket.

---

## Full Pipeline (Per Post)

```
1. Scheduler fires SCAN_FEED task
2. Rate limiter checks: OK to scan?
3. Feed Scanner: open feed, scroll, extract posts
4. For each post:
   a. Deduplication: already in DB? → skip
   b. Relevance Classifier (Groq): score 0-10
   c. Score < threshold? → mark SKIPPED, continue
   d. Viral Detector: high velocity? → elevate priority
   e. Engagement Strategy: decide LIKE / COMMENT / SKIP
   f. Budget Tracker: budget remaining? If not → downgrade
   g. Comment Generator (Groq): generate comment text
   h. Preview mode? → push to UI, await approval
   i. Human Behavior: random delay 8-45s
   j. Interaction Engine: execute action via Playwright
   k. Result: SUCCESS or FAILED (retry once on fail)
   l. Profile visit if score ≥ 8: scrape + email enrichment
   m. Engagement Log: write action record
   n. Budget: increment counter
   o. WebSocket: push live update to dashboard
```

---

## WebSocket Events (backend → frontend)

| Event | Payload | Trigger |
|---|---|---|
| `engine_state` | `{state: "RUNNING"}` | Any state change |
| `activity` | `{action, target, result, comment}` | Every action |
| `budget_update` | `{action_type, count, limit}` | Each action |
| `alert` | `{level, message}` | CAPTCHA / error / limit |
| `post_preview` | `{post_text, author, comment}` | Preview mode |
| `lead_added` | `{name, company, email}` | New lead found |
| `stats_update` | `{scanned, liked, commented, ...}` | Every action |

---

## UI Pages

| Page | Route | Purpose |
|---|---|---|
| Dashboard | / | Engine status, live feed, counters, budget bars |
| Engine Control | /control | Start/stop, module toggles, activity windows |
| Topics | /topics | Topics, hashtags, keywords, industry filters |
| Feed Engagement | /feed | Engagement mode, comment log, re-scan interval |
| Content Studio | /content | Generate + schedule LinkedIn posts |
| Campaigns | /campaigns | Multi-step sequence builder + tracking |
| Leads | /leads | Lead table, email enrichment, CSV export |
| Analytics | /analytics | Charts, performance, weekly summary |
| Prompt Editor | /prompts | Edit + test all AI prompts live |
| Settings | /settings | API keys, rate limits, credentials |

---

## Module Dependency Rules

- `api/` imports from `core/`, `storage/`, `growth/`
- `core/pipeline.py` imports from `automation/`, `ai/`, `growth/`, `enrichment/`, `storage/`
- `automation/` imports from `utils/` only
- `ai/` imports from `utils/` and `storage/` (for prompt loading) only
- `growth/` imports from `ai/`, `storage/`, `core/state_manager` only
- `enrichment/` imports from `storage/`, `utils/` only
- `storage/` imports from `utils/` only
- `utils/` imports nothing internal — zero internal dependencies

Circular imports are forbidden. If you need shared logic, it goes in `utils/`.

---

## Phase 2 Conversion Map (Chrome Extension — do not build yet)

| Phase 1 | Phase 2 Equivalent |
|---|---|
| Playwright browser | Content scripts (content_scripts/*.js) |
| FastAPI + WebSocket | Background service worker |
| React UI (localhost) | Extension options page |
| chrome.storage | SQLite |
| APScheduler | chrome.alarms API |
| Groq fetch calls | Same — fetch from service worker |
| settings.yaml | chrome.storage.sync |
