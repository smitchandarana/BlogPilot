# Phase 2 — BlogPilot Hybrid Platform Plan

## Context

Phase 1 is complete: 8 sprints, M7 validated, ~16k LOC Python backend + React UI running as a local app with Playwright browser automation. The user wants to evolve this into a production-ready product with:

- Chrome Extension interface (sidepanel while browsing LinkedIn)
- Any LLM provider (not just Groq)
- Modular data integrations
- Cleaner, less cluttered UI/UX
- Gmail auth, Stripe payments, data export, lead management

**Why hybrid, not pure extension:** Three blockers kill a pure Chrome Extension approach:
1. Chrome Web Store rejects LinkedIn automation extensions (ToS violation)
2. Content scripts cannot do autonomous automation (no click/type/navigate)
3. MV3 service worker 30s idle timeout kills persistent engines

**Solution:** Extension = UI + passive observer. Native host = existing Python backend. Cloud = auth + billing + sync.

---

## Architecture

```
┌────────────────────────────────────────────────┐
│  Chrome Extension (MV3)                        │
│                                                │
│  Sidepanel UI ──── Popup ──── Content Script   │
│  (React/Vite)      (status)   (LinkedIn DOM    │
│  Dashboard          toggle     MutationObserver │
│  Content Studio     budgets    passive only)    │
│  Leads                                         │
│                                                │
│  Service Worker                                │
│  ├─ Message router (IPC hub)                   │
│  ├─ chrome.alarms (keepalive, status poll)     │
│  ├─ LLM provider router                       │
│  └─ chrome.runtime.connectNative()             │
└────────────────┬───────────────────────────────┘
                 │ Native Messaging (stdio JSON)
                 ▼
┌────────────────────────────────────────────────┐
│  Native Host (Python — Phase 1 backend)        │
│                                                │
│  native_messaging/host.py (stdio adapter)      │
│       ↓ calls existing modules directly        │
│  core/engine.py    → state, scheduler, workers │
│  core/pipeline.py  → feed scan, AI scoring     │
│  automation/*      → Playwright (unchanged)    │
│  ai/*              → Groq/OpenRouter/any LLM   │
│  storage/*         → SQLite (unchanged)        │
│  enrichment/*      → email finding             │
│  growth/*          → campaigns, viral, strategy│
└────────────────┬───────────────────────────────┘
                 │ HTTPS (optional — for SaaS features)
                 ▼
┌────────────────────────────────────────────────┐
│  Cloud Backend (FastAPI — Railway/Render)       │
│                                                │
│  /auth     → Google OAuth + JWT                │
│  /billing  → Stripe subscriptions + webhooks   │
│  /users    → profile, settings, plan limits    │
│  /sync     → cross-device lead/settings sync   │
│  /exports  → CSV / JSON / PDF / Google Sheets  │
│  /webhooks → outbound to Zapier/HubSpot/Notion │
│                                                │
│  PostgreSQL (Supabase)                         │
└────────────────────────────────────────────────┘
```

### Data Flow

```
LinkedIn Page
    │ DOM mutations observed
    ▼
Content Script (passive)
    │ chrome.runtime.sendMessage({ type: 'FEED_POSTS_OBSERVED', posts })
    ▼
Service Worker
    │ bridge.send({ command: 'feed_posts_observed', posts })
    ▼
Native Host (Python)
    │ Passes to pipeline → AI scores → generates comments
    │ Returns results via stdio JSON
    ▼
Service Worker
    │ Broadcasts to all connected ports
    ▼
Sidepanel UI
    │ Shows preview queue, activity feed, budgets
    ▼
User approves comment
    │ chrome.runtime.sendMessage({ type: 'APPROVE_COMMENT' })
    ▼
Service Worker → Native Host → Playwright posts comment
```

---

## Directory Structure

```
BlogPilot/
├── extension/                    # NEW — Chrome Extension
│   ├── manifest.json             # MV3 manifest
│   ├── background/
│   │   ├── service_worker.js     # Message routing, alarms, native bridge
│   │   ├── native_bridge.js      # Native messaging protocol
│   │   ├── storage.js            # chrome.storage wrapper
│   │   └── alarm_scheduler.js    # chrome.alarms wrapper
│   ├── content/
│   │   └── linkedin_observer.js  # Passive MutationObserver on LinkedIn feed
│   ├── popup/
│   │   ├── popup.html
│   │   ├── popup.js              # Quick status + engine toggle
│   │   └── popup.css
│   ├── sidepanel/                # React app (built by Vite → dist/)
│   │   ├── index.html
│   │   ├── src/
│   │   │   ├── App.jsx           # 3-tab layout: Feed / Content / Leads
│   │   │   ├── hooks/
│   │   │   │   ├── useNative.js  # Native host connection state
│   │   │   │   ├── useEngine.js  # Engine state (mirrors Phase 1 hook)
│   │   │   │   └── useBudgets.js # Budget tracking
│   │   │   ├── pages/
│   │   │   │   ├── FeedView.jsx      # Activity + Preview Queue + Budgets
│   │   │   │   ├── ContentView.jsx   # Content Studio (simplified)
│   │   │   │   └── LeadsView.jsx     # Lead table + export
│   │   │   ├── components/
│   │   │   │   ├── EngineToggle.jsx  # Reuse from Phase 1
│   │   │   │   ├── BudgetBar.jsx     # Reuse from Phase 1
│   │   │   │   ├── PreviewQueue.jsx  # Reuse from Phase 1
│   │   │   │   ├── ActivityFeed.jsx  # Reuse from Phase 1
│   │   │   │   └── UpgradeModal.jsx  # Paywall prompt
│   │   │   └── api/
│   │   │       └── bridge.js     # Sends messages to service worker
│   │   ├── vite.config.js
│   │   └── package.json
│   ├── providers/                # LLM provider modules
│   │   ├── index.js              # Provider registry + factory
│   │   ├── groq.js
│   │   ├── openai.js
│   │   ├── anthropic.js
│   │   ├── ollama.js
│   │   ├── openrouter.js
│   │   └── gemini.js
│   └── icons/
│       ├── icon16.png
│       ├── icon48.png
│       └── icon128.png
│
├── backend/                      # EXISTING — Phase 1 (mostly unchanged)
│   ├── native_messaging/         # NEW — stdio adapter for Chrome
│   │   ├── __init__.py
│   │   ├── host.py               # Main entry: reads stdin JSON, dispatches, writes stdout
│   │   ├── protocol.py           # Message framing (4-byte length prefix + JSON)
│   │   ├── dispatcher.py         # Routes commands → existing backend functions
│   │   └── manifest.json         # Chrome native messaging host manifest
│   ├── ai/
│   │   ├── client_factory.py     # MODIFY — add provider abstraction
│   │   ├── providers/            # NEW — pluggable LLM backends
│   │   │   ├── __init__.py
│   │   │   ├── base.py           # Abstract LLMProvider interface
│   │   │   ├── groq_provider.py  # Wraps existing groq_client.py
│   │   │   ├── openai_provider.py
│   │   │   ├── anthropic_provider.py
│   │   │   ├── ollama_provider.py
│   │   │   └── openrouter_provider.py  # Wraps existing openrouter support
│   │   └── ... (existing files unchanged)
│   ├── api/                      # EXISTING — keep for direct HTTP access too
│   └── ... (all other modules unchanged)
│
├── cloud/                        # NEW — SaaS backend
│   ├── main.py                   # FastAPI app
│   ├── api/
│   │   ├── auth.py               # Google OAuth + JWT
│   │   ├── billing.py            # Stripe checkout, portal, webhooks
│   │   ├── users.py              # User CRUD, settings
│   │   ├── sync.py               # Lead/settings cross-device sync
│   │   ├── exports.py            # CSV, JSON, PDF, Google Sheets
│   │   └── webhooks.py           # Outbound: Zapier, HubSpot, Notion
│   ├── models/
│   │   ├── user.py               # User, Subscription
│   │   ├── lead.py               # Cloud lead copy
│   │   └── sync.py               # SyncState tracking
│   ├── services/
│   │   ├── stripe_service.py     # Stripe business logic
│   │   ├── sheets_service.py     # Google Sheets API
│   │   └── pdf_service.py        # PDF report generation
│   ├── db.py                     # Supabase PostgreSQL connection
│   ├── requirements.txt
│   └── Dockerfile
│
├── scripts/
│   ├── install_native_host.py    # NEW — registers native messaging host with Chrome
│   ├── build_extension.py        # NEW — builds sidepanel React + packages extension
│   └── ... (existing scripts)
│
├── ui/                           # EXISTING — Phase 1 standalone UI (kept for dev/desktop mode)
└── ... (existing root files)
```

---

## What Gets Reused vs Rebuilt

### Reused (90%+ of Phase 1)

| Module | Reuse Strategy |
|--------|----------------|
| `backend/core/*` (engine, pipeline, scheduler, workers, state_manager, circuit_breaker, rate_limiter) | Unchanged — native host calls these directly |
| `backend/automation/*` (Playwright, feed_scanner, interaction_engine, human_behavior, post_publisher) | Unchanged — Playwright stays in Python |
| `backend/ai/*` (groq_client, prompt_loader, comment_generator, post_generator, relevance_classifier) | Unchanged + new provider abstraction wrapping them |
| `backend/storage/*` (SQLite, models, budget_tracker, engagement_log, leads_store) | Unchanged |
| `backend/enrichment/*` (email enricher, SMTP, pattern generator) | Unchanged |
| `backend/growth/*` (campaigns, viral, strategy, topic_rotator) | Unchanged |
| `backend/learning/*` (auto_tuner, comment_monitor, calibrator) | Unchanged |
| `backend/research/*` (topic_researcher, reddit/rss/hn scanners) | Unchanged |
| `prompts/*.txt` | Unchanged |
| `config/settings.yaml` | Add new keys for LLM provider, cloud sync |
| `ui/src/components/EngineToggle.jsx` | Copy to sidepanel, adapt props |
| `ui/src/components/BudgetBar.jsx` | Copy to sidepanel |
| `ui/src/components/PreviewQueue.jsx` | Copy to sidepanel |
| `ui/src/components/ActivityFeed.jsx` | Copy to sidepanel |

### New Code

| Module | Purpose | LOC Estimate |
|--------|---------|-------------|
| `extension/background/*` (4 files) | Service worker, native bridge, storage, alarms | ~600 |
| `extension/content/linkedin_observer.js` | Passive feed observer | ~200 |
| `extension/popup/*` | Quick status UI | ~150 |
| `extension/sidepanel/*` (React app) | 3-view sidepanel UI | ~1500 |
| `extension/providers/*` (6 files) | LLM provider modules | ~600 |
| `backend/native_messaging/*` (4 files) | stdio adapter for Chrome | ~500 |
| `backend/ai/providers/*` (6 files) | Python LLM provider abstraction | ~400 |
| `cloud/*` (full SaaS backend) | Auth, billing, sync, exports | ~2000 |
| `scripts/install_native_host.py` | Installer | ~100 |
| `scripts/build_extension.py` | Build script | ~80 |
| **Total new code** | | **~6130** |

### Dropped

| What | Replaced By |
|------|-------------|
| `ui/` as primary interface | `extension/sidepanel/` (but `ui/` kept for desktop dev mode) |
| WebSocket connection model | Native messaging + chrome.runtime ports |
| localhost:8000 API calls from browser | Service worker → native messaging → Python |
| `backend/utils/lock_file.py` relevance | Extension is single-instance by design; lock file stays for desktop mode |

---

## Sprint Plan

### Sprint 2A — Native Messaging Bridge (2 weeks)

**Goal:** Extension talks to existing Python backend via native messaging.

**Files to create:**
1. `extension/manifest.json` — MV3 manifest with permissions
2. `extension/background/service_worker.js` — message routing + native messaging
3. `extension/background/native_bridge.js` — native messaging protocol (JSON over stdio)
4. `extension/background/storage.js` — chrome.storage.local wrapper
5. `extension/background/alarm_scheduler.js` — chrome.alarms wrapper
6. `extension/icons/icon{16,48,128}.png` — placeholder icons
7. `backend/native_messaging/__init__.py`
8. `backend/native_messaging/protocol.py` — 4-byte length prefix + JSON framing
9. `backend/native_messaging/host.py` — stdin/stdout loop, dispatches to backend
10. `backend/native_messaging/dispatcher.py` — command → function mapping for all 91 endpoints
11. `backend/native_messaging/manifest.json` — Chrome native messaging host manifest
12. `scripts/install_native_host.py` — registers host with Chrome (writes registry key on Windows)

**Key decisions:**
- Native messaging host name: `com.blogpilot.backend`
- Protocol: Chrome's native messaging uses 4-byte little-endian length prefix + JSON payload
- Dispatcher maps command strings to existing backend functions (e.g., `engine_start` → `engine.start()`)
- Host.py runs as a subprocess spawned by Chrome — it imports existing backend modules directly

**Acceptance criteria:**
- Load extension in Chrome (developer mode)
- Extension service worker connects to native host
- `engine_status` command returns real engine state
- `engine_start` / `engine_stop` work through the bridge
- Keepalive alarm prevents service worker termination

**Dependencies:** None (builds on existing backend)

---

### Sprint 2B — Sidepanel UI (2 weeks)

**Goal:** React sidepanel with 3 views replaces the 10-page localhost app.

**Files to create:**
1. `extension/sidepanel/index.html` — entry point
2. `extension/sidepanel/package.json` — React + Vite + Tailwind (subset of current ui/)
3. `extension/sidepanel/vite.config.js` — builds to extension/sidepanel/dist/
4. `extension/sidepanel/src/App.jsx` — 3-tab layout (Feed / Content / Leads)
5. `extension/sidepanel/src/api/bridge.js` — sends messages via chrome.runtime
6. `extension/sidepanel/src/hooks/useNative.js` — native host connection state
7. `extension/sidepanel/src/hooks/useEngine.js` — mirrors Phase 1 useEngine.js
8. `extension/sidepanel/src/hooks/useBudgets.js` — budget state from events
9. `extension/sidepanel/src/pages/FeedView.jsx` — EngineToggle + PreviewQueue + BudgetBars + ActivityFeed
10. `extension/sidepanel/src/pages/ContentView.jsx` — Topic selector + generate + schedule (simplified ContentStudio)
11. `extension/sidepanel/src/pages/LeadsView.jsx` — Lead table + export button
12. `extension/sidepanel/src/components/` — port EngineToggle, BudgetBar, PreviewQueue, ActivityFeed from ui/src/

**Files to create (popup):**
13. `extension/popup/popup.html`
14. `extension/popup/popup.js` — engine state indicator + toggle button + "Open Sidepanel" button
15. `extension/popup/popup.css`

**UI/UX design principles:**
- **3 views only** — Feed (engagement), Content (generation), Leads (CRM)
- **No sidebar nav** — bottom tab bar (mobile-style, fits sidepanel width ~400px)
- **Progressive disclosure** — advanced settings behind gear icon, not visible by default
- **Status bar** — persistent top bar showing engine state (green/yellow/red dot) + native host connection
- **Compact cards** — preview queue items are condensed (post snippet + comment + approve/reject)
- **Command palette** — Cmd+K to search actions (generate, scan, export, settings)

**Acceptance criteria:**
- Sidepanel opens alongside LinkedIn
- EngineToggle starts/stops engine through native bridge
- PreviewQueue shows pending comments, approve/reject works
- BudgetBars update in real-time from native host events
- ActivityFeed shows live actions
- ContentView can generate a post
- LeadsView shows lead list from native host

**Dependencies:** Sprint 2A (native messaging bridge must work)

---

### Sprint 2C — Passive Content Script + LLM Abstraction (2 weeks)

**Goal:** Extension passively observes LinkedIn feed + users can pick any LLM.

**Content script files:**
1. `extension/content/linkedin_observer.js` — MutationObserver on LinkedIn feed DOM

**Content script behavior:**
- Runs on `https://www.linkedin.com/*` at `document_idle`
- Sets up MutationObserver on feed container
- When new post elements appear in DOM, extracts: author, text, like count, URL
- Sends extracted posts to service worker: `{ type: 'FEED_POSTS_OBSERVED', posts: [...] }`
- **NO clicks, NO typing, NO scrolling, NO DOM modification**
- Zero `web_accessible_resources` (prevents LinkedIn fingerprinting)
- Minimal DOM footprint (no injected elements)

**LLM provider files (extension side):**
2. `extension/providers/index.js` — provider registry
3. `extension/providers/groq.js`
4. `extension/providers/openai.js`
5. `extension/providers/anthropic.js`
6. `extension/providers/ollama.js`
7. `extension/providers/openrouter.js`
8. `extension/providers/gemini.js`

**LLM provider files (Python side):**
9. `backend/ai/providers/__init__.py`
10. `backend/ai/providers/base.py` — abstract `LLMProvider` interface
11. `backend/ai/providers/groq_provider.py` — wraps existing `groq_client.py`
12. `backend/ai/providers/openai_provider.py`
13. `backend/ai/providers/anthropic_provider.py`
14. `backend/ai/providers/ollama_provider.py`
15. `backend/ai/providers/openrouter_provider.py`
16. `backend/ai/client_factory.py` — MODIFY to use provider registry

**LLM Provider Interface:**
```
class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, system: str, user: str, **opts) -> str: ...

    @abstractmethod
    async def complete_json(self, system: str, user: str, **opts) -> dict: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def supports_json_mode(self) -> bool: ...
```

**Two routing modes:**
1. **Native mode** (default): Extension → service worker → native host → Python LLM provider → API
2. **Direct mode**: Extension → service worker → `fetch()` to LLM API directly (bypasses native host for lower latency)

**Acceptance criteria:**
- LinkedIn feed posts appear in sidepanel without user action (passive observation)
- User can switch LLM provider in settings (Groq → OpenAI → Anthropic → Ollama)
- Comment generation works with any selected provider
- Ollama (local) works without internet
- Provider API keys stored in chrome.storage.local (encrypted)

**Dependencies:** Sprint 2A + 2B

---

### Sprint 2D — Cloud Backend + Google Auth (3 weeks)

**Goal:** Users sign in with Google, settings sync across devices.

**Files to create:**
1. `cloud/main.py` — FastAPI app with CORS
2. `cloud/db.py` — Supabase PostgreSQL connection
3. `cloud/api/auth.py` — Google OAuth endpoints
4. `cloud/api/users.py` — User CRUD
5. `cloud/api/sync.py` — Settings + leads sync
6. `cloud/models/user.py` — User, Subscription SQLAlchemy models
7. `cloud/models/lead.py` — Cloud lead copy
8. `cloud/models/sync.py` — SyncState tracking
9. `cloud/requirements.txt`
10. `cloud/Dockerfile`
11. `cloud/alembic/` — database migrations

**Auth flow:**
```
1. User clicks "Sign in with Google" in sidepanel
2. Extension calls chrome.identity.launchWebAuthFlow()
3. Google returns OAuth code
4. Extension sends code to cloud: POST /auth/google
5. Cloud exchanges code for Google tokens
6. Cloud creates/finds user, generates JWT
7. Extension stores JWT in chrome.storage.local
8. All cloud API calls include Authorization: Bearer <jwt>
9. JWT refresh: cloud issues refresh token, extension auto-refreshes
```

**Sync strategy:**
- **Settings sync:** On change → POST /sync/settings (debounced 5s). On startup → GET /sync/settings (merge with local).
- **Lead sync:** Bidirectional. Cloud is source of truth. Local leads push to cloud on create. Conflict resolution: latest timestamp wins.
- **Not synced:** Engine state, budget counters, action logs (these are local machine state)

**Acceptance criteria:**
- User can sign in with Google from sidepanel
- Settings persist across Chrome profiles / devices
- Leads sync to cloud
- Unauthenticated users can still use the extension (local-only mode)

**Dependencies:** Sprint 2A-2C (extension must be functional first)

---

### Sprint 2E — Stripe Payments (2 weeks)

**Goal:** Three pricing tiers with plan-gated features.

**Files to create/modify:**
1. `cloud/api/billing.py` — Stripe Checkout, Customer Portal, webhook handler
2. `cloud/services/stripe_service.py` — Stripe business logic
3. `extension/sidepanel/src/pages/BillingView.jsx` — Plan display + upgrade
4. `extension/sidepanel/src/components/UpgradeModal.jsx` — Paywall prompt
5. `extension/background/plan_guard.js` — Plan limit checker

**Pricing tiers:**

| Feature | Free | Pro ($29/mo) | Business ($79/mo) |
|---------|------|-------------|-------------------|
| Comments/day | 5 | 50 | Unlimited |
| Topics | 3 | 15 | Unlimited |
| LLM providers | Groq only | Any | Any |
| Email enrichment | No | Yes | Yes |
| CSV export | No | Yes | Yes |
| PDF reports | No | No | Yes |
| Google Sheets sync | No | No | Yes |
| CRM integrations | No | No | Yes |
| Team seats | 1 | 1 | 5 |

**Plan gating implementation:**
- Service worker checks plan before executing commands
- Native host also checks (defense in depth)
- Cloud webhook updates plan on payment events
- Upgrade modal shows when limit hit (not before)

**Stripe flow:**
```
1. User clicks "Upgrade to Pro" in BillingView
2. Extension opens Stripe Checkout (cloud generates session URL)
3. User completes payment on Stripe
4. Stripe webhook → cloud updates subscription
5. Cloud pushes new plan to extension via JWT refresh
6. Extension unlocks gated features
```

**Acceptance criteria:**
- Free tier works without payment
- Upgrade flow opens Stripe Checkout
- Plan limits enforced (5 comments/day on free)
- Downgrade revokes features gracefully
- Webhook handles payment failures

**Dependencies:** Sprint 2D (auth must work — billing ties to user)

---

### Sprint 2F — Exports + Integrations (2 weeks)

**Goal:** Multiple export formats + outbound integrations.

**Files to create:**
1. `cloud/api/exports.py` — Export endpoints
2. `cloud/services/pdf_service.py` — PDF report generation (WeasyPrint or ReportLab)
3. `cloud/services/sheets_service.py` — Google Sheets API integration
4. `cloud/api/webhooks.py` — Outbound webhook management

**Export formats:**

| Format | Implementation | Plan |
|--------|---------------|------|
| CSV | Already exists (leads_store.to_csv) — wire to cloud | Pro |
| JSON | New: structured lead + analytics dump | Pro |
| PDF | New: weekly analytics report with charts (server-side) | Business |
| Google Sheets | New: live sync via Sheets API (push on lead create/update) | Business |

**Integrations (outbound webhooks):**

| Integration | Method | Plan |
|-------------|--------|------|
| Zapier | Outbound webhook on lead/action events | Business |
| HubSpot | Direct API: create/update contacts | Business |
| Notion | Direct API: append to database | Business |
| Custom webhook | POST to user-defined URL | Pro |

**Webhook architecture:**
- User configures webhook URL + events to listen for (lead_added, comment_posted, etc.)
- Cloud queues webhook deliveries (retry 3x with backoff)
- Webhook payload: standard JSON with event type + data

**Acceptance criteria:**
- CSV export downloads from sidepanel
- JSON export returns structured data
- PDF weekly report generates with real charts
- Google Sheets: new leads appear in user's sheet within 60s
- Zapier webhook fires on configured events

**Dependencies:** Sprint 2D-2E (auth + billing for plan gating)

---

### Sprint 2G — Onboarding + Installer (2 weeks)

**Goal:** Smooth first-run experience + native host installation.

**Files to create:**
1. `scripts/install_native_host.py` — ENHANCE: full installer with Chrome detection, registry writes, PATH setup
2. `scripts/build_extension.py` — builds sidepanel React + packages extension as .zip/.crx
3. `extension/sidepanel/src/components/OnboardingWizard.jsx` — guided first-run flow
4. Installer: `installer/blogpilot_setup.iss` (Inno Setup) or `installer/blogpilot.nsi` (NSIS)

**Onboarding flow (first launch):**
```
Step 1: "Welcome to BlogPilot" → Google sign-in (or "Continue without account")
Step 2: "Choose your plan" → Free / Pro / Business (or "Start free")
Step 3: "Add your AI key" → Groq (free, default) / OpenAI / Anthropic / Ollama
Step 4: "Pick 3-5 topics" → topic selector with suggestions
Step 5: "Connect LinkedIn" → guided credential entry (encrypted)
Step 6: "Start your first scan" → engine starts, shows first results
```

**Native host installer (Windows):**
```
1. Copies Python backend to Program Files/BlogPilot/
2. Creates native messaging manifest JSON
3. Writes Chrome registry key: HKCU\Software\Google\Chrome\NativeMessagingHosts\com.blogpilot.backend
4. Points manifest to Python entry point
5. Optionally creates Start Menu shortcut for standalone mode
```

**Distribution plan:**
- Extension: `.zip` sideload instructions (Chrome developer mode)
- Native host: Windows installer (Inno Setup — already have `installer.iss`)
- Combined: single installer that deploys both

**Auto-update mechanism:**
- Extension: manual (user re-downloads .zip) or GitHub Releases RSS
- Native host: built-in update checker (calls GitHub API for latest release)
- Cloud: deployed via Railway/Render CI/CD

**Acceptance criteria:**
- Fresh Chrome install → load extension → onboarding wizard guides through setup
- Native host installer works on Windows 10/11
- Extension detects when native host is not installed and shows install instructions
- "Continue without account" works (local-only mode)

**Dependencies:** All previous sprints

---

### Sprint 2H — Polish + GDPR + Testing (2 weeks)

**Goal:** Production-ready quality.

**Tasks:**

1. **GDPR compliance:**
   - Privacy policy page (required for Google OAuth)
   - Data deletion endpoint: DELETE /users/me → removes all cloud data
   - Export my data endpoint: GET /users/me/export → full JSON dump
   - Cookie consent not needed (extension, not website)
   - LinkedIn data disclaimer in onboarding

2. **Error reporting:**
   - Sentry integration in extension (service worker + sidepanel)
   - Sentry integration in cloud backend
   - Error boundary components in React

3. **Testing:**
   - Extension E2E tests (Puppeteer controlling Chrome with extension loaded)
   - Native messaging integration tests (mock stdio)
   - Cloud API tests (pytest + httpx)
   - Stripe webhook tests (mock webhook events)

4. **UI polish:**
   - Loading skeletons throughout sidepanel
   - Empty states (no leads, no activity, no comments)
   - Error states (native host disconnected, API timeout)
   - Dark mode support (follows Chrome system preference)

5. **Performance:**
   - Sidepanel React bundle size < 200KB gzipped
   - Content script < 10KB (minimal footprint on LinkedIn)
   - Native messaging latency < 100ms for simple commands

**Acceptance criteria:**
- Privacy policy URL configured in Google OAuth consent screen
- User can delete all their data from settings
- Sentry captures errors from extension + cloud
- All tests pass
- Bundle sizes within targets

**Dependencies:** All previous sprints

---

## Technology Stack

| Layer | Tech | Reason |
|-------|------|--------|
| Extension | Manifest V3 | Required for Chrome |
| Sidepanel UI | React 18 + Vite + Tailwind | Reuse Phase 1 components |
| Service Worker | Vanilla JS (ES modules) | MV3 constraint (no bundler complexity) |
| Native Host | Python 3.11+ | Reuse entire Phase 1 backend |
| Cloud API | FastAPI + Pydantic | Team knowledge, async support |
| Cloud DB | Supabase (PostgreSQL) | Auth + DB + Realtime |
| Auth | Google OAuth + chrome.identity | Gmail auth, no passwords |
| Payments | Stripe | Industry standard |
| LLM abstraction | Provider interface (Python + JS) | Swap without code change |
| PDF export | WeasyPrint or ReportLab | Python-native, no extra service |
| Sheets integration | Google Sheets API v4 | Direct API, no middleware |
| Error tracking | Sentry | Best extension support |
| Analytics | PostHog | Privacy-first product analytics |
| Cloud hosting | Railway | Simple FastAPI deploys |
| Extension distribution | Sideloaded .zip + installer | CWS not viable for LinkedIn tools |

---

## Risk Register

| Risk | Severity | Mitigation |
|------|----------|------------|
| LinkedIn detects content script | HIGH | Zero `web_accessible_resources`, no DOM injection, passive MutationObserver only, randomized observation intervals |
| MV3 service worker timeout | MEDIUM | `chrome.runtime.connectNative()` cancels both timers; keepalive alarm at 30s |
| Native host installation friction | HIGH | Single-click installer (Inno Setup); clear onboarding instructions; "works without native host" degraded mode (manual copy-paste comments) |
| Stripe webhook reliability | LOW | Cloud handles it; retry queue with exponential backoff |
| Google OAuth in extension | LOW | `chrome.identity.launchWebAuthFlow` is well-documented, stable API |
| User account suspension by LinkedIn | MEDIUM | All automation via Playwright (separate browser), extension is passive UI only; circuit breaker + budget limits as Phase 1 |
| Cross-platform support (Mac/Linux) | MEDIUM | Native host installer needs platform-specific paths; defer Mac/Linux to Sprint 2I |
| Supabase cold starts | LOW | Railway always-on dyno for paid plans; health check endpoint |

---

## Timeline Summary

| Sprint | Duration | Focus | Deliverable |
|--------|----------|-------|-------------|
| **2A** | 2 weeks | Foundation | Native messaging bridge works, extension loads |
| **2B** | 2 weeks | UI | Sidepanel 3-view app, popup toggle |
| **2C** | 2 weeks | Intelligence | Passive LinkedIn observer, multi-LLM support |
| **2D** | 3 weeks | Cloud | Google auth, user accounts, settings sync |
| **2E** | 2 weeks | Revenue | Stripe 3-tier billing, plan gating |
| **2F** | 2 weeks | Data | CSV/JSON/PDF/Sheets export, webhook integrations |
| **2G** | 2 weeks | Distribution | Installer, onboarding wizard, auto-updates |
| **2H** | 2 weeks | Quality | GDPR, Sentry, tests, dark mode, performance |
| **Total** | **17 weeks** | | |

---

## Verification Plan

### After Sprint 2A:
- Load extension in `chrome://extensions` (developer mode)
- Open DevTools → service worker console → verify "BlogPilot service worker loaded"
- Start Python backend → verify "Native host connected" in service worker console
- Send `engine_status` → verify JSON response with engine state

### After Sprint 2B:
- Open LinkedIn → click extension icon → sidepanel opens
- Click "Start Engine" → engine starts (green dot)
- Activity feed shows real events
- Preview queue shows pending comments
- Approve a comment → comment posts to LinkedIn

### After Sprint 2C:
- Browse LinkedIn feed → sidepanel shows observed posts count
- Settings → change LLM to OpenAI → generate comment → uses OpenAI
- Settings → change LLM to Ollama → generate comment → uses local model

### After Sprint 2D:
- Click "Sign in with Google" → Google OAuth popup → JWT stored
- Change a setting → sign in on different Chrome profile → setting synced

### After Sprint 2E:
- Free user hits 5 comments → upgrade modal appears
- Click upgrade → Stripe Checkout → payment → limits unlocked

### After Sprint 2F:
- Export leads as CSV → file downloads
- Export leads as PDF → formatted report downloads
- Configure Zapier webhook → create lead → webhook fires

### After Sprint 2G:
- Fresh Chrome → load extension → onboarding wizard starts
- Run installer → native host registered → extension connects automatically

### After Sprint 2H:
- Trigger error → appears in Sentry
- Delete account → all cloud data removed
- Lighthouse audit on sidepanel → performance score > 90

---

## Key Files to Modify (Existing)

| File | Change |
|------|--------|
| `backend/ai/client_factory.py` | Add provider registry, `get_provider(name)` factory |
| `config/settings.yaml` | Add `llm_provider`, `cloud_sync`, `billing` sections |
| `backend/main.py` | Add native messaging detection (skip HTTP server when run as native host) |
| `installer.iss` | Update to include native messaging host registration |
| `TASKS.md` | Add Phase 2 sprint tracking |

## Key Files to Read Before Each Sprint

| Sprint | Read These First |
|--------|-----------------|
| 2A | `backend/main.py`, `backend/core/engine.py`, `backend/api/engine.py` |
| 2B | `ui/src/pages/Dashboard.jsx`, `ui/src/components/EngineToggle.jsx`, `ui/src/hooks/useEngine.js` |
| 2C | `backend/automation/feed_scanner.py`, `backend/ai/groq_client.py`, `backend/ai/client_factory.py` |
| 2D | `backend/api/websocket.py` (for auth pattern), Google Identity API docs |
| 2E | Stripe Checkout docs, `cloud/api/auth.py` (for user model) |
| 2F | `backend/storage/leads_store.py` (to_csv), Google Sheets API v4 docs |
| 2G | `installer.iss`, Chrome native messaging docs |
| 2H | Sentry Chrome Extension SDK docs |
