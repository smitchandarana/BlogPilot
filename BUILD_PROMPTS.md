# Build Prompts — LinkedIn AI Growth Engine
# Copy-paste each prompt into Claude Code exactly as written.
# Switch models using /model before each session.
# Run /clear between sprints to reset context.

---

## MODEL GUIDE

| Model | Use When | Speed | Token Cost |
|---|---|---|---|
| **Sonnet 4.6** | Writing modules, UI components, wiring API to frontend, tests | Fast | Low |
| **Opus 4.6** | Architecture decisions, complex multi-file logic, debugging, reviews | Slow | High |
| **Haiku 4.5** | Boilerplate files, simple edits, config files, quick fixes | Fastest | Lowest |
| **opusplan** | Use this alias for any task >5 files — plans with Opus, builds with Sonnet | Auto | Balanced |

**Default for this project: Sonnet 4.6**
Use `opusplan` for Sprint 3 (core engine) and Sprint 4 (browser automation).
Use `Opus 4.6` for architecture review sessions only.
Use `Haiku 4.5` for tests, configs, and simple utility files.

---

## TOKEN OPTIMIZATION RULES

1. **Start every session with:** `Read CONTEXT.md` — NOT ARCHITECTURE.md. CONTEXT.md is 80% smaller.
2. **Use /clear between sprints.** Never carry context from Sprint 1 into Sprint 3.
3. **Reference files, don't repeat them.** Say "see CONTEXT.md line 45" not paste the content.
4. **One module per prompt.** Don't ask for 5 files at once. One file = one focused prompt.
5. **Use /compact at 50% context.** Don't wait until you're at 80%.
6. **Pin the task.** Start every prompt with exactly what file is being built.
7. **Give examples, not explanations.** Show one existing module as a pattern instead of describing the pattern.

---

## PRE-SESSION CHECKLIST
Run these before every Claude Code session:

```bash
# Check what's already built
cat TASKS.md | grep -E "\[x\]|\[~\]"

# Check current DB state (after Sprint 1)
python -c "from storage.database import init_db; init_db(); print('DB OK')"

# Check backend is running
curl -s localhost:8000/health | python -m json.tool
```

---
---

# SPRINT 1 — Project Foundation

## Session 1A — Backend Scaffold
**Model: Sonnet 4.6**
**Estimated tokens: ~8k**
**Files: 3**

```
Read CONTEXT.md.
Read TASKS.md.

Build these 3 files in order:

1. backend/main.py
   - FastAPI app with CORS (allow localhost:3000)
   - Register routers: api/engine, api/config, api/analytics, api/campaigns, api/leads, api/websocket
   - Mount WebSocket at /ws
   - GET /health endpoint returns {"status": "ok", "engine_state": state_manager.get()}
   - Boot sequence: init_db() → load_config() → acquire_lock() → start scheduler

2. backend/utils/logger.py
   - get_logger(name: str) → logging.Logger
   - JSON structured output with: timestamp, level, module, message
   - File handler: logs/engine.log (rotating, max 10MB, keep 5)
   - Console handler with colour coding by level

3. backend/utils/config_loader.py
   - load_config() → dict: reads config/settings.yaml
   - get(key: str, default=None): dot-notation access e.g. get("engine.enabled")
   - watch(): starts watchdog FileSystemEventHandler, calls load_config() on change
   - Singleton pattern — one config instance shared across app

After building each file, run it to verify no import errors.
Mark each complete in TASKS.md with [x].
```

---

## Session 1B — Utils + Lock File
**Model: Haiku 4.5**
**Estimated tokens: ~4k**
**Files: 2**

```
Read CONTEXT.md section "Key Rules".

Build these 2 utility files:

1. backend/utils/encryption.py
   - Uses cryptography.fernet.Fernet
   - Key derived from machine hostname + fixed salt (so key is machine-specific)
   - encrypt(plaintext: str) → str (base64 encoded)
   - decrypt(ciphertext: str) → str
   - Key stored in config/.secrets.key on first run
   - If .secrets.key missing, generate and save new key

2. backend/utils/lock_file.py
   - Lock file path: /tmp/linkedin_engine.lock
   - acquire() → bool: write PID to lock file, return True if acquired
   - release(): delete lock file
   - is_locked() → bool: check if lock file exists and PID is alive
   - Call release() on SIGTERM and SIGINT

Test both files with simple unit tests in tests/test_utils.py.
Mark complete in TASKS.md.
```

---

## Session 1C — Storage Layer
**Model: Sonnet 4.6**
**Estimated tokens: ~12k**
**Files: 6**

```
Read CONTEXT.md section "DB Tables".

Build the full storage layer. Build in this exact order (dependencies first):

1. backend/storage/database.py
   - SQLAlchemy engine: sqlite:///./data/engine.db
   - SessionLocal = sessionmaker(...)
   - Base = declarative_base()
   - init_db(): creates all tables, seeds budget rows from config daily_budget values
   - get_db(): context manager yielding session, always closes

2. backend/storage/models.py
   - All 7 ORM models from CONTEXT.md "DB Tables" section
   - Use proper types: String, Integer, Float, DateTime, Text, JSON
   - All DateTime fields default=datetime.utcnow
   - Post.id = SHA256(url), generated on __init__

3. backend/storage/post_state.py
   - is_seen(url: str, db) → bool
   - mark_seen(url: str, db) → Post
   - update_state(url: str, state: str, db, **kwargs) → Post
   - get_recent_posts(limit: int, db) → List[Post]

4. backend/storage/engagement_log.py
   - write_action(action_type, target_url, target_name, result, db, comment_text=None, error_msg=None)
   - get_recent(n: int, db) → List[ActionLog]
   - get_stats_today(db) → dict {action_type: count}

5. backend/storage/budget_tracker.py
   - check(action_type: str, db) → bool (True = under budget, OK to proceed)
   - increment(action_type: str, db)
   - reset_all(db): called at midnight, resets all count_today to 0
   - get_all(db) → List[Budget]
   - Schedule midnight reset using APScheduler (imported from core/scheduler when available)

6. backend/storage/leads_store.py
   - create_lead(data: dict, db) → Lead (upsert by linkedin_url)
   - update_email(lead_id: str, email: str, status: str, method: str, db)
   - get_all(db, filters: dict = None) → List[Lead]
   - get_by_id(lead_id: str, db) → Lead
   - to_csv(leads: List[Lead]) → str

Write tests/test_storage.py covering: init_db, create post, mark seen, budget check/increment, budget reset, create lead.
Mark all complete in TASKS.md.
```

---

## Session 1D — API Skeleton + WebSocket
**Model: Sonnet 4.6**
**Estimated tokens: ~10k**
**Files: 6**

```
Read CONTEXT.md sections "Module → File Map" (api lines) and "WebSocket Events".

Build all 6 API files as skeletons — correct routes, correct response shapes, stub implementations.
Actual logic is wired in later sprints. For now return mock/placeholder data.

1. backend/api/engine.py
   - POST /engine/start → {"state": "RUNNING"}
   - POST /engine/stop → {"state": "STOPPED"}
   - POST /engine/pause → {"state": "PAUSED"}
   - POST /engine/resume → {"state": "RUNNING"}
   - GET /engine/status → {"state": str, "uptime_seconds": int, "tasks_queued": int}

2. backend/api/config.py
   - GET/POST /topics → list of topic strings
   - GET/PUT /settings → full settings dict
   - GET /prompts → {name: text} for all 5 prompts
   - PUT /prompts/{name} → update single prompt text
   - POST /prompts/test → {prompt_name, variables} → {"output": str}

3. backend/api/analytics.py
   - GET /analytics/daily → {date, actions: {type: count}, leads_found: int}
   - GET /analytics/weekly → 7 days of daily data
   - GET /analytics/top-topics → [{topic, engagement_count}]
   - GET /analytics/summary → AI-generated text summary (stub: "Summary coming soon")

4. backend/api/campaigns.py
   - GET/POST /campaigns
   - GET/PUT/DELETE /campaigns/{id}
   - POST /campaigns/{id}/enroll → {lead_ids: List[str]}
   - GET /campaigns/{id}/stats → {enrolled, in_progress, completed, reply_rate}

5. backend/api/leads.py
   - GET /leads → List with optional ?status= ?company= filters
   - GET /leads/{id}
   - POST /leads/{id}/enrich → trigger email enrichment (stub)
   - POST /leads/enrich-all → trigger bulk enrichment (stub)
   - GET /leads/export → CSV file response

6. backend/api/websocket.py
   - WebSocket endpoint at /ws
   - ConnectionManager class: connect, disconnect, broadcast(event, payload)
   - broadcast_activity(action, target, result, comment=None)
   - broadcast_state_change(state)
   - broadcast_budget_update(action_type, count, limit)
   - broadcast_alert(level, message)
   - broadcast_lead_added(name, company, email)

Test: run uvicorn, hit /health, /engine/status, /leads — all should return valid JSON.
Mark complete in TASKS.md.
```

---

## Session 1E — Frontend Scaffold
**Model: Sonnet 4.6**
**Estimated tokens: ~10k**
**Files: 5**

```
Read CONTEXT.md section "UI Pages → Routes".

Build the React scaffold. All pages are empty shells for now — just routing and layout.

1. ui/package.json
   Dependencies: react@18, react-dom@18, react-router-dom@6, @vitejs/plugin-react,
   vite, tailwindcss, autoprefixer, postcss, recharts, axios, lucide-react

2. ui/src/api/client.js
   - axios instance: baseURL=http://localhost:8000
   - engine: { start, stop, pause, resume, status }
   - config: { getTopics, updateTopics, getSettings, updateSettings, getPrompts, updatePrompt, testPrompt }
   - analytics: { daily, weekly, topTopics, summary }
   - campaigns: { list, create, update, delete, enroll, stats }
   - leads: { list, get, enrich, enrichAll, export }

3. ui/src/hooks/useWebSocket.js
   - Connect to ws://localhost:8000/ws
   - Auto-reconnect on disconnect (exponential backoff, max 30s)
   - on(event, callback): subscribe to specific event types
   - Expose: isConnected, lastEvent, subscribe/unsubscribe

4. ui/src/hooks/useEngine.js
   - Uses client.engine and useWebSocket
   - state: {status: "STOPPED", uptime: 0, tasksQueued: 0}
   - actions: start(), stop(), pause(), resume()
   - Auto-updates state from WebSocket engine_state events

5. ui/src/components/Layout.jsx + ui/src/App.jsx
   - Sidebar nav with all 10 routes and icons (lucide-react)
   - Active route highlighted
   - App.jsx: BrowserRouter + Routes for all 10 pages (all render "<PageName> — Coming Soon" for now)
   - Small engine status indicator in nav (green dot = RUNNING, yellow = PAUSED, grey = STOPPED)

Run: npm run dev — verify all 10 routes load without errors.
Mark complete in TASKS.md.
```

---
---

# SPRINT 2 — UI All Screens

> **Run /clear before starting Sprint 2.**
> **Model: Sonnet 4.6 for all UI work.**

## Session 2A — Dashboard + Engine Control
**Model: Sonnet 4.6**
**Estimated tokens: ~14k**
**Files: 4**

```
Read CONTEXT.md.
Reference existing ui/src/hooks/useEngine.js and ui/src/hooks/useWebSocket.js.

Build these 4 UI components with REAL wiring to the API hooks (use mock data where API isn't built yet):

1. ui/src/components/EngineToggle.jsx
   - Large prominent button: shows current state
   - STOPPED → green "Start Engine" button
   - RUNNING → red "Stop" + yellow "Pause" buttons side by side
   - PAUSED → green "Resume" + red "Stop" buttons
   - Loading spinner during state transitions
   - Uses useEngine() hook

2. ui/src/components/BudgetBar.jsx
   Props: actionType, count, limit, color
   - Horizontal progress bar
   - Shows "12 / 30 comments" label
   - Color: green < 60%, yellow 60-85%, red > 85%
   - Animated fill

3. ui/src/components/ActivityFeed.jsx
   - Scrolling log of last 50 activities
   - Each entry: icon (action type) + target name + result badge + timestamp
   - Green badge = SUCCESS, red = FAILED, grey = SKIPPED
   - Auto-scrolls to bottom on new entry
   - Uses useWebSocket() hook, listens for "activity" events

4. ui/src/pages/Dashboard.jsx
   Layout:
   - Top row: EngineToggle (full width)
   - Second row: 6 stat counters (posts scanned, liked, commented, profiles visited, emails found, leads)
   - Third row: 6 BudgetBar components (one per action type)
   - Main area: ActivityFeed (last 50 actions)
   - Alert banner (shows when WebSocket "alert" event received)
   All data from useEngine() and useWebSocket() hooks.

5. ui/src/pages/EngineControl.jsx
   - Module toggles: feed_engagement, campaigns, content_studio, email_enrichment (from config API)
   - Activity window: start_hour, end_hour time pickers
   - Day checkboxes: Mon Tue Wed Thu Fri Sat Sun
   - Feed scan interval: number input (minutes)
   - Circuit breaker settings: error threshold, pause duration
   - Save button → PUT /settings
   - All values from GET /settings on load

Mark complete in TASKS.md.
```

---

## Session 2B — Topics, Feed, Content Studio
**Model: Sonnet 4.6**
**Estimated tokens: ~14k**
**Files: 3**

```
Read CONTEXT.md.

Build these 3 pages. Wire to API client where endpoints exist, mock data elsewhere.

1. ui/src/pages/Topics.jsx
   - Topic tags section: display as pills with X to remove, text input + Add button
   - Hashtag list: same pattern
   - Keyword blacklist: same pattern
   - Industry filter: multi-select checkboxes
   - Minimum relevance score: slider 0-10 with numeric display
   - Influencer watchlist: text input for LinkedIn URL, add/remove list
   - Competitor watchlist: same
   - Save button → PUT /topics + PUT /settings for threshold
   - Load from GET /topics + GET /settings

2. ui/src/pages/FeedEngagement.jsx
   - Engagement mode: 4-option radio buttons (like_only/comment_only/like_and_comment/smart)
   - Preview comments toggle: on/off switch
   - Viral detection threshold: number input
   - Re-scan interval: number input (minutes)
   - Recent posts table: columns = Author, Post snippet (40 chars), Score, Action, Result, Time
   - Skipped posts table: same but with "Reason skipped" column
   - Comment history table: Author, Comment text, Post link, Posted at

3. ui/src/pages/ContentStudio.jsx
   - Topic selector: dropdown (from /topics)
   - Style selector: Thought Leadership / Story / Tips List / Question / Data Insight / Contrarian Take
   - Tone selector: Professional / Conversational / Bold / Educational
   - Word count: slider 80-300
   - Generate button → POST /prompts/test with post prompt
   - Generated post textarea: editable, character counter (3000 max)
   - Regenerate button
   - Post Now button (stub — Phase 4)
   - Schedule button: date/time picker (stub)
   - Post queue table: Scheduled time, Topic, Style, Status (Scheduled/Posted/Failed)

Mark complete in TASKS.md.
```

---

## Session 2C — Campaigns, Leads, Analytics
**Model: Sonnet 4.6**
**Estimated tokens: ~16k**
**Files: 4**

```
Read CONTEXT.md sections "DB Tables" (campaigns, leads) and "UI Pages → Routes".

Build these 4 pages:

1. ui/src/components/CampaignBuilder.jsx
   - List of step cards (drag to reorder — use simple up/down buttons, no drag library needed)
   - Add Step button: dropdown of types: Visit / Follow / Connect / Message / InMail / Endorse / Wait
   - Each step card: type icon + config fields (message text for Message/InMail, days for Wait)
   - Message fields support variables: {first_name} {company} {title} shown as blue chips below input
   - AI Write button on message fields → calls POST /prompts/test with note prompt

2. ui/src/pages/Campaigns.jsx
   - Campaign list: name, status badge, enrolled count, reply rate, created date
   - New Campaign button → modal with CampaignBuilder + name input
   - Click campaign → expand stats: enrolled/in_progress/completed/replied funnel chart
   - Pause/Resume/Delete per campaign
   - Enroll button → paste LinkedIn URLs textarea → POST /campaigns/{id}/enroll

3. ui/src/pages/Leads.jsx
   - Table: First Name, Last Name, Title, Company, LinkedIn (link), Email, Email Status badge, Source, Actions
   - Email Status badges: NOT_FOUND=grey, FOUND=blue, VERIFIED=green, BOUNCED=red
   - Filter bar: search input, email status dropdown, company input
   - Enrich button per row → POST /leads/{id}/enrich
   - Bulk Enrich All button → POST /leads/enrich-all
   - Export CSV button → GET /leads/export (file download)
   - Enroll in Campaign button → campaign selector dropdown → POST /campaigns/{id}/enroll

4. ui/src/pages/Analytics.jsx
   Use Recharts for all charts.
   - Daily actions bar chart (7d/30d toggle): grouped bars per action type
   - Top topics bar chart: topic vs engagement count
   - Email find rate: simple stat card (% of leads with email found)
   - Connection acceptance rate: stat card
   - Campaign funnel: horizontal bar chart (enrolled/connected/replied/converted)
   - Weekly summary text card (from GET /analytics/summary)
   All data from /analytics endpoints, loading skeleton while fetching.

Mark complete in TASKS.md.
```

---

## Session 2D — Prompt Editor + Settings
**Model: Sonnet 4.6**
**Estimated tokens: ~10k**
**Files: 3**

```
Read CONTEXT.md section "Module → File Map" (ai/ lines) and PROMPTS.md variable table.

1. ui/src/components/PromptTestPanel.jsx
   - Left side: textarea for sample post input
   - Variable inputs: auto-detected from prompt text (scan for {variable_name} patterns)
   - Run Test button → POST /prompts/test → show result in right panel
   - Right side: AI output display with copy button
   - Loading state with spinner

2. ui/src/pages/PromptEditor.jsx
   - Left sidebar: list of 5 prompt names (relevance, comment, post, note, reply)
   - Click → loads prompt text in main editor
   - Main editor: large textarea with monospace font, line numbers, character count
   - Variable reference panel: shows all {variables} detected in current prompt as chips
   - Save button → PUT /prompts/{name}
   - Reset to Default button → GET /prompts/{name}/default (add this endpoint stub)
   - PromptTestPanel below editor for live testing

3. ui/src/pages/Settings.jsx
   Sections:
   - AI Config: Groq API key (password input + Test Connection button), model selector, temperature slider
   - LinkedIn: credentials section with note "Stored encrypted. Never shown in plaintext."
   - Rate Limits: per-action daily limit inputs (table of action_type + limit input)
   - Delays: min/max sliders for each delay type
   - Browser: headless toggle, profile path input, stealth toggle
   - Storage: DB path display, log retention days input
   - Danger Zone: red section with "Clear All Data" button (confirmation required)
   All data from GET /settings. Save → PUT /settings.

Mark complete in TASKS.md.
```

---

## Sprint 2 Review
**Model: Opus 4.6**
**Estimated tokens: ~6k**
**This is an analysis prompt, not a build prompt.**

```
Read CONTEXT.md.
Do NOT write any code. Analysis only.

Review the complete UI by navigating to each of the 10 pages.
For each page report:
1. Does it load without errors?
2. Are all listed features present (check against CONTEXT.md UI Pages)?
3. Any broken layouts or missing components?
4. Any API calls that would fail in production (wrong endpoint, wrong shape)?

Then provide a prioritised fix list. Mark any issues that would break Sprint 3 wiring as CRITICAL.
```

---
---

# SPRINT 3 — Core Engine

> **Run /clear before Sprint 3.**
> **Use opusplan alias for this entire sprint — complex multi-file logic.**

## Session 3A — State Manager + Task Queue
**Model: opusplan**
**Estimated tokens: ~10k**
**Files: 2**

```
Read CONTEXT.md sections "State Machine" and "Module → File Map" (core/ lines).

Build these 2 files. They are the foundation everything else depends on:

1. backend/core/state_manager.py
   - EngineState enum: STOPPED, RUNNING, PAUSED, ERROR
   - StateManager class (singleton)
   - get() → EngineState
   - start() → raises if not STOPPED
   - stop() → works from RUNNING or PAUSED, drains queue first
   - pause() → only from RUNNING
   - resume() → only from PAUSED
   - set_error(reason: str) → sets ERROR state, logs reason
   - recover() → only from ERROR, goes to STOPPED
   - All transitions logged via utils/logger.py
   - Thread-safe (use threading.Lock)

2. backend/core/task_queue.py
   - Priority enum: HIGH, NORMAL
   - Task dataclass: id(UUID), type(str), payload(dict), priority, created_at, retries=0
   - TaskQueue class
   - put(task: Task): adds to queue (high priority at front)
   - get() → Task: blocks waiting for task
   - get_nowait() → Task | None
   - size() → int
   - drain(): blocks until queue empty (used by stop())
   - is_empty() → bool
   - Uses queue.PriorityQueue internally

Test: tests/test_core_state.py
- Test all valid transitions
- Test invalid transitions raise ValueError
- Test thread safety: 10 threads calling start() simultaneously, only one succeeds
Mark complete in TASKS.md.
```

---

## Session 3B — Worker Pool + Scheduler
**Model: opusplan**
**Estimated tokens: ~10k**
**Files: 2**

```
Read CONTEXT.md. Read backend/core/state_manager.py and backend/core/task_queue.py first.

Build these 2 files:

1. backend/core/worker_pool.py
   - WorkerPool class
   - __init__(max_workers=3, queue: TaskQueue, state_manager: StateManager)
   - start(): launches worker threads (NOT process pool — thread pool only)
   - stop(): signals workers to stop after current task, joins threads
   - _worker_loop(): runs in thread, pulls from queue, calls _execute(task)
   - _execute(task): dispatches task.type to registered handlers
   - register_handler(task_type: str, fn: Callable): register task type handlers
   - submit(task_type: str, payload: dict, priority=NORMAL): create Task, put in queue
   - active_count() → int: currently executing tasks
   - Workers check state_manager: if PAUSED, sleep and retry. If STOPPED, exit.

2. backend/core/scheduler.py
   - Uses APScheduler with SQLAlchemyJobStore (SQLite for persistence across restarts)
   - Scheduler class
   - start(): start APScheduler
   - stop()
   - schedule_feed_scan(interval_minutes: int): recurring job → submit SCAN_FEED to queue
   - schedule_midnight_reset(): daily at 00:01 → calls budget_tracker.reset_all()
   - schedule_influencer_check(interval_minutes: int): recurring → submit CHECK_INFLUENCERS
   - reschedule_feed_scan(new_interval): update interval without restart
   - Reads interval from config_loader on each fire (so config changes take effect)

Test: tests/test_core_worker.py
- Submit 10 tasks, verify all execute
- Submit while PAUSED, verify tasks queue but don't execute
- Resume, verify queued tasks execute
Mark complete in TASKS.md.
```

---

## Session 3C — Rate Limiter + Circuit Breaker + Engine
**Model: opusplan**
**Estimated tokens: ~12k**
**Files: 3**

```
Read CONTEXT.md. Read all existing core/ files first.

1. backend/core/rate_limiter.py
   - RateLimiter class
   - Uses in-memory sliding window (deque per action type)
   - check(action_type: str) → bool: True = under hourly cap, OK to proceed
   - record(action_type: str): record that action was taken now
   - Limits from config: rate_limits.{likes_per_hour|comments_per_hour|...}
   - Thread-safe

2. backend/core/circuit_breaker.py
   - CircuitBreaker class
   - record_error(reason: str): add to error deque, check threshold
   - record_success(): reset consecutive error count
   - is_tripped() → bool
   - reset(): manually reset after investigation
   - If errors ≥ threshold within window_minutes:
     → call state_manager.pause()
     → broadcast_alert("critical", "Circuit breaker tripped: {reason}")
     → schedule auto-resume after pause_duration_minutes
   - CAPTCHA-specific: if reason contains "captcha" → action = config circuit_breaker.captcha_detected_action

3. backend/core/engine.py
   - Engine class (main singleton)
   - Owns: state_manager, task_queue, worker_pool, scheduler, rate_limiter, circuit_breaker
   - start(): acquire lock → init DB → load config → start scheduler → start worker pool → state=RUNNING
   - stop(): state=STOPPED → drain queue → stop workers → stop scheduler → release lock
   - pause(): state=PAUSED (workers keep running but won't pick new tasks)
   - resume(): state=RUNNING
   - status() → dict: state, uptime, tasks_queued, active_workers, today_stats
   - Wire API routes (api/engine.py) to call engine singleton methods

4. Wire api/engine.py to actual engine singleton
   - Import engine singleton
   - Each endpoint calls engine.start() / stop() / pause() / resume() / status()
   - Return real state, not mock

5. Wire WebSocket broadcast calls:
   - engine state changes → websocket.broadcast_state_change(state)
   - circuit_breaker trips → websocket.broadcast_alert("critical", msg)

Test: run full engine start→pause→resume→stop sequence. Verify WebSocket sends events.
Milestone 2 check: Start/stop/pause/resume work via UI. WebSocket shows live state in Dashboard.
Mark complete in TASKS.md.
```

---
---

# SPRINT 4 — Browser Automation

> **Run /clear before Sprint 4.**
> **Use opusplan. This is the highest-risk code in the project.**

## Session 4A — Browser + Login
**Model: opusplan**
**Estimated tokens: ~12k**
**Files: 2**

```
Read CONTEXT.md.
Read backend/utils/encryption.py and backend/utils/config_loader.py.

Build these 2 files carefully. LinkedIn detection risk is highest here.

1. backend/automation/browser.py
   - BrowserManager class (singleton)
   - Uses playwright.async_api (async Playwright)
   - launch(): launch browser with these exact stealth settings:
     * args: --disable-blink-features=AutomationControlled
     * args: --disable-infobars
     * args: --no-sandbox
     * user_data_dir: config browser.profile_path (persistent profile)
     * viewport: {width: config viewport_width, height: config viewport_height}
   - After launch, inject JS: Object.defineProperty(navigator, 'webdriver', {get: () => undefined})
   - get_page() → Page: returns current page or opens new one
   - close(): gracefully close browser
   - is_running() → bool
   - Headless mode from config browser.headless

2. backend/automation/linkedin_login.py
   - LinkedInLogin class
   - login(page, email: str, password: str): navigate to linkedin.com/login, fill credentials, submit
   - Credentials via utils/encryption.decrypt() — never plaintext
   - save_cookies(page, path): save session cookies to config/.cookies.json (encrypted)
   - load_cookies(page, path): load and apply saved cookies
   - is_logged_in(page) → bool: check for feed/nav elements
   - detect_reauth_needed(page) → bool: check for login page redirect
   - handle_security_challenge(page): detect CAPTCHA/email verify → pause engine → alert UI
   - Full retry logic: try cookie load first, fall back to credential login

Test manually: run browser.launch() + login() + is_logged_in() → should return True.
DO NOT run automated tests against LinkedIn. Manual verification only for auth.
Mark complete in TASKS.md.
```

---

## Session 4B — Feed Scanner + Human Behavior
**Model: Sonnet 4.6**
**Estimated tokens: ~12k**
**Files: 2**

```
Read CONTEXT.md. Read backend/automation/browser.py.

1. backend/automation/human_behavior.py
   Build these helper functions (used by ALL automation modules):
   - random_delay(min_s: float, max_s: float): asyncio.sleep with gaussian distribution
   - type_slowly(page, selector: str, text: str): type char-by-char at random WPM from config
   - scroll_down(page, passes: int): scroll down N times with random pauses between
   - hover_before_click(page, selector: str): hover 0.3-1.2s before clicking
   - All timing from config delays section via config_loader.get()

2. backend/automation/feed_scanner.py
   - FeedScanner class
   - scan(page) → List[dict]: full feed scan, returns raw post data
   - _scroll_feed(page): scroll config feed_engagement.scroll_passes times
   - _extract_posts(page) → List[dict]: parse DOM
     Each post dict: {url, author_name, author_url, text, like_count, comment_count, timestamp}
   - LinkedIn DOM selectors (as of 2025):
     Post container: div[data-urn]
     Author name: span.update-components-actor__name
     Post text: div.feed-shared-update-v2__description
     Like count: button[aria-label*="reaction"] span
     URL: a[href*="/feed/update/"] or a[href*="/posts/"]
   - _clean_text(text: str): strip HTML, normalize whitespace
   - Deduplication: call post_state.is_seen() for each, skip seen posts
   - Returns only NEW, unseen posts
   - Max posts per scan: config feed_engagement.max_posts_per_scan

Write tests/test_feed_scanner.py with mock page object.
Mark complete in TASKS.md.
```

---

## Session 4C — Interaction Engine + Profile Scraper
**Model: opusplan**
**Estimated tokens: ~14k**
**Files: 2**

```
Read CONTEXT.md. Read backend/automation/human_behavior.py.
Read backend/core/budget_tracker.py and backend/core/circuit_breaker.py.

CRITICAL: Every action in interaction_engine.py MUST:
1. Check budget_tracker.check(action_type) before executing
2. Call human_behavior.random_delay() before executing
3. Call circuit_breaker.record_success() on success
4. Call circuit_breaker.record_error() on exception
5. Retry ONCE on failure before marking FAILED

1. backend/automation/interaction_engine.py
   - InteractionEngine class
   - async like_post(page, post_url: str) → bool
     Navigate to post → find like button → hover → click → verify liked
   - async comment_post(page, post_url: str, comment_text: str) → bool
     Navigate to post → click comment box → type_slowly(comment_text) → submit → verify posted
   - async connect_with(page, profile_url: str, note: str = None) → bool
     Navigate to profile → find Connect button → click → if note: add note → confirm
   - async follow(page, profile_url: str) → bool
   - async endorse_skills(page, profile_url: str) → bool
   - async send_message(page, profile_url: str, message: str) → bool
   - All methods log to engagement_log.write_action() on completion

2. backend/automation/profile_scraper.py
   - ProfileScraper class
   - async scrape(page, profile_url: str) → dict
     Returns: {first_name, last_name, title, company, company_domain, email, connection_degree, linkedin_url}
   - _extract_email(page) → str|None: find email in contact info section (visible to 1st degree)
   - _extract_degree(page) → int: look for "1st", "2nd", "3rd" degree indicators
   - _extract_company_domain(company_name: str) → str: simple domain inference from company name
   - After scrape: call leads_store.create_lead(data) to save

Test manually. Mark complete in TASKS.md.
Milestone 3 check: Engine opens browser, logs in, reads 10+ posts, posts appear in Feed log in UI.
```

---

## Session 4D — Pipeline + Post Publisher
**Model: opusplan**
**Estimated tokens: ~16k**
**Files: 2**

```
Read CONTEXT.md section "Pipeline Steps". Read ALL automation and core modules.
This is the most important file in the project.

1. backend/core/pipeline.py
   Full implementation of all 17 pipeline steps from CONTEXT.md.
   
   Pipeline class:
   - __init__(browser, feed_scanner, interaction_engine, profile_scraper,
              relevance_classifier, comment_generator, engagement_strategy,
              viral_detector, email_enricher, engagement_log, budget_tracker,
              post_state, websocket, config): dependency injection
   - async run_feed_scan(): execute full pipeline for one feed scan
   - async _process_post(post: dict): process a single post through all steps
   - async _handle_preview(post, comment): push to UI, wait for approval (30s timeout)
   - All steps from CONTEXT.md pipeline in exact order
   - Comprehensive logging at each step
   - Emit WebSocket events: activity, budget_update, lead_added, stats_update

2. backend/automation/post_publisher.py
   - PostPublisher class
   - async publish(page, post_text: str) → bool
     Navigate to LinkedIn home → click "Start a post" → type_slowly(post_text) → Post button
   - Verify post appeared in feed after submit
   - Used by ContentStudio schedule queue

Register pipeline as SCAN_FEED handler in worker_pool.
Wire ContentStudio "Post Now" button via API.

Milestone 4 check: Full AI pipeline — post → score → comment → log → dashboard update.
Mark complete in TASKS.md.
```

---
---

# SPRINT 5 — AI Layer

> **Run /clear before Sprint 5.**
> **Model: Sonnet 4.6 for all AI module files.**

## Session 5A — Groq Client + Prompt Loader
**Model: Sonnet 4.6**
**Estimated tokens: ~8k**
**Files: 2**

```
Read CONTEXT.md section "Module → File Map" (ai/ lines).

1. backend/ai/groq_client.py
   - GroqClient class
   - __init__(api_key: str, model: str, max_tokens: int, temperature: float)
   - async complete(system: str, user: str) → str
   - Retry logic: 2 attempts, exponential backoff (2s, 4s), using tenacity
   - Rate limit detection: if 429 response → sleep 60s → retry
   - Timeout: 30s per request
   - Log every call: model, input tokens (estimate), latency
   - Raise GroqError on unrecoverable failure

2. backend/ai/prompt_loader.py
   - PromptLoader class (singleton)
   - load_all(): read all 5 prompts from prompts/*.txt into memory dict
   - get(name: str) → str: return prompt template text
   - format(name: str, **kwargs) → str: fill {variables} in template
   - watch(): watchdog on prompts/ directory, reload on any .txt file change
   - reset_to_default(name: str): copy from prompts/{name}.txt.default if exists
   - get_variables(name: str) → List[str]: extract all {variable} names from template

Test both with real Groq API call (needs GROQ_API_KEY in env).
tests/test_ai_client.py: mock Groq HTTP, test retry logic and error handling.
Mark complete in TASKS.md.
```

---

## Session 5B — All 5 AI Modules
**Model: Sonnet 4.6**
**Estimated tokens: ~12k**
**Files: 5**

```
Read CONTEXT.md. Read PROMPTS.md variable table section.
Read backend/ai/groq_client.py and backend/ai/prompt_loader.py.

Build all 5 AI modules. Each follows the same pattern:
- Takes GroqClient and PromptLoader via dependency injection
- Formats the correct prompt using prompt_loader.format(name, **kwargs)
- Calls groq_client.complete(system, user)
- Parses and returns result

1. backend/ai/relevance_classifier.py
   async classify(post_text, author_name, topics: str) → {score: float, reason: str}
   Parse JSON from Groq response. If JSON parse fails, return score=0, reason="parse_error".

2. backend/ai/comment_generator.py
   async generate(post_text, author_name, topics: str, tone="professional") → str
   Return plain text comment. Strip quotes if model wraps in them.

3. backend/ai/post_generator.py
   async generate(topic, style, tone, word_count=150) → str
   Return plain text post ready for LinkedIn.

4. backend/ai/note_writer.py
   async generate(first_name, title, company, shared_context, topics) → str
   Must be under 300 chars. If over, truncate at last complete sentence.

5. backend/ai/reply_generator.py
   async generate(original_post, your_comment, reply_to_comment, replier_name) → str

Wire:
- relevance_classifier and comment_generator into pipeline.py (replace stubs)
- post_generator into api/config.py POST /prompts/test with post prompt
- note_writer into campaign_engine.py (for auto-generated notes)

Wire Prompt Editor "Test" button to actual AI calls via POST /prompts/test endpoint.

Milestone 4 check: Full AI pipeline end-to-end. Comment visible in preview panel.
Mark complete in TASKS.md.
```

---
---

# SPRINT 6 — Email Enrichment

> **Run /clear before Sprint 6.**
> **Model: Sonnet 4.6**

## Session 6 — Full Email Layer
**Model: Sonnet 4.6**
**Estimated tokens: ~14k**
**Files: 5**

```
Read CONTEXT.md section "Module → File Map" (enrichment/ lines).
Read backend/storage/leads_store.py.

Build the complete email enrichment layer:

1. backend/enrichment/dom_email_scraper.py
   - async scrape(page) → str|None
   - Click "Contact info" link on profile page
   - Find email in modal DOM: look for mailto: links or elements with @ symbol
   - Close modal after extraction
   - Returns email string or None

2. backend/enrichment/pattern_generator.py
   - generate(first_name: str, last_name: str, domain: str) → List[str]
   - Generate these patterns in order:
     first.last@domain, f.last@domain, first@domain, flast@domain,
     firstl@domain, last@domain, first_last@domain, f_last@domain
   - Normalize names: lowercase, remove accents, remove special chars
   - Return deduplicated list

3. backend/enrichment/smtp_verifier.py
   - async verify(email: str) → bool
   - Step 1: MX record lookup via dnspython
   - Step 2: SMTP EHLO + RCPT TO handshake (no mail sent)
   - Timeout: config email_enrichment.smtp_timeout_seconds
   - Return True if server accepts RCPT TO (250 response)
   - Catch all exceptions → return False
   - Never actually send email

4. backend/enrichment/hunter_client.py
   - async find(first_name, last_name, domain) → str|None
   - Only runs if config email_enrichment.use_hunter_api = True
   - GET https://api.hunter.io/v2/email-finder with API key from secrets
   - Return email string or None
   - Graceful fail if no API key

5. backend/enrichment/email_enricher.py
   - EmailEnricher class (orchestrator)
   - async enrich(page, profile_data: dict) → {email, status, method}
   - Order of methods (stop at first success):
     1. DOM scraper (if connection_degree == 1 and use_dom_scraper config)
     2. Hunter.io API (if use_hunter_api config)
     3. Pattern generator + SMTP verifier for each pattern (if use_pattern_generator config)
   - Returns {email: str|None, status: NOT_FOUND|FOUND|VERIFIED, method: DOM|HUNTER|PATTERN|SMTP}

Wire enricher into pipeline.py: after profile_scraper on score ≥ 8 posts.
Wire to api/leads.py enrich endpoints.

Test: tests/test_enrichment.py
- Mock SMTP server, verify verify() returns True on 250
- Test pattern generator output for "John Smith" @ "tcs.com"
- Test orchestrator tries methods in order, stops at first success

Milestone 6 check: Email found → in Leads table → in CSV export.
Mark complete in TASKS.md.
```

---
---

# SPRINT 7 — Campaigns + Growth

> **Run /clear before Sprint 7.**
> **Model: opusplan**

## Session 7A — Viral + Strategy + Influencer
**Model: Sonnet 4.6**
**Estimated tokens: ~10k**
**Files: 3**

```
Read CONTEXT.md.

1. backend/growth/viral_detector.py
   - is_viral(like_count, comment_count, post_timestamp) → bool
   - Calculate likes_per_hour = like_count / hours_since_posted
   - Compare to config viral_detection thresholds
   - get_priority(is_viral: bool) → Priority.HIGH | Priority.NORMAL

2. backend/growth/engagement_strategy.py
   - decide(score: float, budget_remaining: dict, mode: str) → str (LIKE|COMMENT|SKIP)
   - mode=like_only → always LIKE if score ≥ threshold
   - mode=comment_only → always COMMENT if score ≥ threshold
   - mode=like_and_comment → LIKE+COMMENT if score ≥ threshold
   - mode=smart → score 6-7: LIKE only, score 8+: LIKE+COMMENT
   - If COMMENT but comment budget exhausted → downgrade to LIKE
   - If LIKE but like budget exhausted → SKIP

3. backend/growth/influencer_monitor.py
   - InfluencerMonitor class
   - async check_all(page) → List[dict]: visit each watchlist profile, get latest post URL
   - Submit as HIGH priority SCAN_POST tasks for any new posts not in DB
   - Watchlist from config/settings.yaml influencer_watchlist or topics DB

Mark complete in TASKS.md.
```

---

## Session 7B — Campaign Engine
**Model: opusplan**
**Estimated tokens: ~14k**
**Files: 1**

```
Read CONTEXT.md. Read backend/storage/models.py (Campaign + CampaignEnrollment).
Read backend/automation/interaction_engine.py.

backend/growth/campaign_engine.py
- CampaignEngine class
- Campaign steps: each step is {type, config, delay_days_after_prev}
  Step types: VISIT_PROFILE, FOLLOW, CONNECT, MESSAGE, INMAIL, ENDORSE, WAIT
- enroll(lead_id: str, campaign_id: str, db): create CampaignEnrollment, set current_step=0, next_action_at=now
- async process_due_enrollments(page, db): find all enrollments where next_action_at <= now and status=IN_PROGRESS
- async execute_step(enrollment, page, db):
  Get lead from DB, get step config, execute via interaction_engine, 
  advance to next step, set next_action_at = now + step.delay_days_after_prev,
  if last step: mark COMPLETED
- async _execute_step_type(step_type, lead, config, page): dispatches to correct interaction_engine method
- For MESSAGE/INMAIL steps: use note_writer.generate() if no message text configured
- Wire PROCESS_CAMPAIGNS task to scheduler (check every 30 minutes)

Test: tests/test_campaigns.py
- Create campaign with 3 steps
- Enroll a mock lead
- Advance time, verify steps execute in order
Mark complete in TASKS.md.
```

---
---

# SPRINT 8 — Analytics + Polish + Testing

> **Run /clear before Sprint 8.**

## Session 8A — Analytics Wiring
**Model: Sonnet 4.6**
**Estimated tokens: ~10k**

```
Read CONTEXT.md. Read backend/storage/engagement_log.py and backend/storage/leads_store.py.

Wire all Analytics page charts to real data:

1. backend/api/analytics.py — full implementation (replace stubs):
   - GET /analytics/daily: query actions_log grouped by action_type for today
   - GET /analytics/weekly: 7 days of daily grouped stats
   - GET /analytics/top-topics: this requires tagging actions with topic — add topic_tag column to ActionLog model
   - GET /analytics/campaign-funnel: query campaign_enrollments for conversion stats
   - GET /analytics/summary: call post_generator with "weekly_summary" style + real stats injected

2. Wire ui/src/pages/Analytics.jsx to real /analytics endpoints (remove mock data).

3. Wire Dashboard.jsx counters to real GET /engine/status data.

4. Wire BudgetBar components to real WebSocket budget_update events.
```

---

## Session 8B — End-to-End Test + README
**Model: Opus 4.6**
**Estimated tokens: ~8k**
**This is a review + test prompt.**

```
Read CONTEXT.md. Read TASKS.md.

Do the following in order:

1. Run the complete milestone checklist from TASKS.md. For each milestone not yet marked [x]:
   - Identify exactly what is missing
   - List the specific file and function that needs to be built or fixed

2. Write tests/test_e2e.py:
   - Mock Playwright, mock Groq API
   - Test: engine starts → scheduler fires → feed scan task queued → pipeline processes 1 mock post
   - Verify: post in DB with state ACTED, action in actions_log, budget incremented, WebSocket event fired
   - Test: budget exhausted → pipeline skips action → state = SKIPPED in DB

3. Write tests/test_budget_safety.py:
   - Verify budget check is called before EVERY action type
   - Verify midnight reset clears all counts
   - Verify circuit breaker trips after threshold errors

4. Update README.md with real setup instructions based on actual requirements.txt and file structure.

5. Final TASKS.md update: mark everything complete that passes tests.
```

---

## Session 8C — Milestone 7 Final Run
**Model: Sonnet 4.6**
**This is an execution prompt, not a build prompt.**

```
Read CONTEXT.md. Read TASKS.md. Check all [x] items.

Start the full engine and run for 5 minutes:
1. python backend/main.py
2. npm run dev (in ui/)
3. Open localhost:3000
4. Click Start Engine
5. Monitor Dashboard for 5 minutes

After the run, check:
- actions_log table: any rows? types correct?
- posts table: any rows? states correct?
- budget table: counts incremented?
- WebSocket: activity events appearing in real time?

Report any errors. Fix them. Repeat until clean.

Milestone 7 target: engine runs without crash, budget enforced, logs clean.
```

---
---

# QUICK REFERENCE

## Session Start Template
```
/model sonnet  (or opus/haiku/opusplan)
Read CONTEXT.md.
Read TASKS.md — note what is [x] complete and what is next.
[paste sprint prompt below]
```

## Mid-Session Commands
```
/compact           at 50% context — summarise and continue
/clear             between sprints — full reset
/model opus        switch to opus for complex debugging
/model sonnet      switch back for implementation
```

## Test Command Per Module
```bash
pytest tests/test_{module}.py -v           # single module
pytest tests/ -v --tb=short               # all tests
pytest tests/ -k "not test_e2e" -v        # skip slow e2e
```

## Token Budget Per Session
```
Sprint 1 sessions:  8k-12k tokens each
Sprint 2 sessions:  10k-16k tokens each  
Sprint 3 sessions:  10k-16k tokens each (use opusplan)
Sprint 4 sessions:  12k-16k tokens each (use opusplan)
Sprint 5 sessions:  8k-12k tokens each
Sprint 6 sessions:  14k tokens
Sprint 7 sessions:  10k-14k tokens each (use opusplan)
Sprint 8 sessions:  8k-10k tokens each

Total estimated: ~120k-160k tokens for complete build
```

## Model Selection Summary
```
Haiku 4.5   → utils files, config files, boilerplate, simple tests
Sonnet 4.6  → UI components, API routes, AI modules, storage layer, most code
opusplan    → core engine, browser automation, pipeline, campaign engine
Opus 4.6    → architecture reviews, debugging multi-file issues, final review
```
