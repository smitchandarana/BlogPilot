# CONTEXT — Quick Reference (Token-Optimised)

This file is the fast-lookup index. Use it to find things without reading full docs.
Full details live in the files referenced. Only load what you need.

---

## Where Things Live

| What | File |
|---|---|
| System design, DB schema, all modules | ARCHITECTURE.md |
| What is built / what to build next | TASKS.md |
| AI prompt templates + variables | PROMPTS.md |
| Default topics, hashtags, job titles | TOPICS.md |
| All config values (rate limits, delays, budget) | config/settings.yaml |

---

## Module → File Map (one line each)

```
engine state FSM          → backend/core/state_manager.py
task queue                → backend/core/task_queue.py
worker pool (max 3)       → backend/core/worker_pool.py
APScheduler jobs          → backend/core/scheduler.py
per-action rate caps      → backend/core/rate_limiter.py
auto-pause on errors      → backend/core/circuit_breaker.py (auto-resumes after pause_duration_minutes)
full pipeline logic       → backend/core/pipeline.py
FastAPI routes            → backend/api/ (engine, config, analytics, campaigns, leads, research, websocket, server)
WebSocket broadcaster     → backend/api/websocket.py
server process control    → backend/api/server.py
Playwright browser        → backend/automation/browser.py
LinkedIn login/cookies    → backend/automation/linkedin_login.py
feed DOM extraction       → backend/automation/feed_scanner.py
profile visit/scrape      → backend/automation/profile_scraper.py
like/comment/connect      → backend/automation/interaction_engine.py
random delays/typing      → backend/automation/human_behavior.py
post publishing           → backend/automation/post_publisher.py
hashtag/search scanning   → backend/automation/hashtag_scanner.py
Groq API wrapper          → backend/ai/groq_client.py
prompt file loader        → backend/ai/prompt_loader.py
score post 0-10           → backend/ai/relevance_classifier.py
generate comment          → backend/ai/comment_generator.py
generate post             → backend/ai/post_generator.py
connection note           → backend/ai/note_writer.py
thread reply              → backend/ai/reply_generator.py
viral velocity check      → backend/growth/viral_detector.py
watch specific profiles   → backend/growth/influencer_monitor.py
decide like/comment/skip  → backend/growth/engagement_strategy.py
multi-step sequences      → backend/growth/campaign_engine.py
topic rotation            → backend/growth/topic_rotator.py
email orchestrator        → backend/enrichment/email_enricher.py
1st degree DOM email      → backend/enrichment/dom_email_scraper.py
pattern generation        → backend/enrichment/pattern_generator.py
SMTP verify               → backend/enrichment/smtp_verifier.py
Hunter.io optional        → backend/enrichment/hunter_client.py
SQLite connection/session → backend/storage/database.py
ORM models (all tables)   → backend/storage/models.py
post seen/acted/skipped   → backend/storage/post_state.py
log every action          → backend/storage/engagement_log.py
daily budget counters     → backend/storage/budget_tracker.py
lead CRUD                 → backend/storage/leads_store.py
quality metrics logging   → backend/storage/quality_log.py
comment reply monitor     → backend/learning/comment_monitor.py
score calibration         → backend/learning/scoring_calibrator.py
timing analysis           → backend/learning/timing_analyzer.py
auto-tune thresholds      → backend/learning/auto_tuner.py
topic research orchestr.  → backend/research/topic_researcher.py
Reddit scanner            → backend/research/reddit_scanner.py
RSS/Atom scanner          → backend/research/rss_scanner.py
Hacker News scanner       → backend/research/hn_scanner.py
LinkedIn feed insights    → backend/research/linkedin_insights.py
duplicate detector        → backend/research/duplicate_detector.py
logger factory            → backend/utils/logger.py
Fernet encryption         → backend/utils/encryption.py
YAML config + hot-reload  → backend/utils/config_loader.py
single instance lock      → backend/utils/lock_file.py
```

---

## DB Tables (names only)

`posts` `leads` `actions_log` `campaigns` `campaign_enrollments` `budget` `settings` `researched_topics` `research_snippets` `scheduled_posts` `comment_quality_log` `post_quality_log` `topic_performance`

Full schema → ARCHITECTURE.md § Database Schema

---

## Engine States

`STOPPED → RUNNING → PAUSED → RUNNING → STOPPED`
`RUNNING → ERROR → STOPPED`

All transitions via `core/state_manager.py` only.

---

## Daily Budget Defaults

```
likes: 30/day    comments: 12/day    connections: 15/day
visits: 50/day   inmails: 5/day      posts: 5/day
```

---

## Pipeline Order (12 steps)

```
1. Scheduler → 2. Feed Scan (+Hashtag/Search Scan) → 3. Deduplicate
4. AI Score → 5. Topic Match → 6. Viral Check → 7. Strategy Decision
8. Comment Generate → 9. Human Delay → 10. Execute Action
11. Quality Log + Topic Tracking → 12. Log + WebSocket Push
```

Profile visit + email enrichment triggered if score ≥ 8.
Hashtag/search scanning runs after home feed scan (config-gated).

---

## Comment Approval Flow

When `feed_engagement.preview_comments: true` (default), comments are NOT posted automatically.
Pipeline stores comment as `state=PREVIEW` in DB and broadcasts `post_preview` WS event.
Dashboard `PreviewQueue` panel shows pending cards — user can edit, approve, or reject.

```
Approve → POST /engine/approve-comment → run_approve_comment() → worker → browser posts comment → state=ACTED
Reject  → POST /engine/reject-comment  → state=SKIPPED (no browser)
Load    → GET  /engine/pending-previews → returns all PREVIEW posts from DB
```

UI component: `ui/src/components/PreviewQueue.jsx`
Entry point:  `backend/core/pipeline.py :: run_approve_comment(post_id, comment_text)`

---

## WebSocket Events

`engine_state | activity | budget_update | alert | post_preview | lead_added | stats_update`

All pushed via `api/websocket.py`

---

## Server Control Endpoints

```
POST /server/restart   → graceful engine stop + os.execv() re-exec
POST /server/shutdown  → graceful engine stop + process exit
GET  /server/info      → PID, uptime, python version
```

UI: Settings → Danger Zone (restart/shutdown buttons with confirmation modals)

---

## UI Pages → Routes

```
Dashboard /  |  Control /control  |  Topics /topics  |  Feed /feed
Content /content  |  Campaigns /campaigns  |  Leads /leads
Analytics /analytics  |  Prompts /prompts  |  Settings /settings
```

---

## Dependency Rules (no circular imports)

```
api → core, storage, growth, learning
core/pipeline → automation, ai, growth, enrichment, storage
automation → utils only
ai → utils, storage only
growth → ai, storage, core/state_manager only
learning → storage, utils, ai only
enrichment → storage, utils only
storage → utils only
utils → nothing internal
```

---

## Hard Constraints

- Max 3 worker threads
- Check budget_tracker before every automation action
- All state transitions through state_manager only
- All WebSocket pushes through api/websocket.py only
- All logging via utils/logger.py get_logger(__name__)
- Credentials encrypted via utils/encryption.py
- Prompts from prompts/*.txt via ai/prompt_loader.py
- Topics from config/settings.yaml
- Phase 2 not started until Milestone 7

---

## Research Pipeline

```
1. Fetch from Reddit, RSS, HN, LinkedIn (parallel)
2. Domain-filter snippets per broad topic (from settings.yaml)
3. AI extract specific subtopics (Groq via topic_extractor prompt)
4. Deduplicate subtopics across domains
5. Score each subtopic (Groq via topic_scorer prompt)
6. Quality gate (drop if composite_score < min_subtopic_score)
7. Store as ResearchedTopic + ResearchSnippet records
```

Broad topics from settings.yaml are domain filters only.
AI extracts specific subtopics like "EDA", "KPI design", "Cohort analysis".
Each ResearchedTopic has a `domain` field linking to its parent broad category.

---

## Prompt Variables

```
relevance:        {post_text} {author_name} {topics}
comment:          {post_text} {author_name} {topics} {tone}
post:             {topic} {style} {tone} {word_count}
note:             {first_name} {title} {company} {shared_context} {topics}
reply:            {original_post} {your_comment} {reply_to_comment} {replier_name}
topic_extractor:  {domain} {snippet_count} {snippets_summary}
topic_scorer:     {topic} {snippet_count} {snippets_summary} {engagement_history}
```

---

## Self-Learning Pipeline

```
1. Pipeline posts comment → quality_log.log_comment() stores score, angle, candidates
2. Pipeline matches topic → topic_rotator.record_engagement() tracks per-topic performance
3. Comment Monitor (4h scheduler): revisits posts → checks for replies → updates got_reply
4. Scoring Calibrator: groups posts by score bucket → calculates engagement rates → recommends threshold
5. Timing Analyzer: groups actions by hour/day → finds best engagement windows
6. Auto-Tuner (24h scheduler): adjusts min_relevance_score ±0.5/cycle, narrows activity hours
7. Comment Generator: queries best angle from engagement data → enriches prompts
```

Scheduler jobs: `comment_monitor` (4h ±600s jitter), `auto_tune` (24h ±3600s jitter).
Auto-tuner also runs on engine start if stale (>24h since last tune).
All learning features gated by `learning.enabled` config.

---

## Learning API Endpoints

```
GET /analytics/learning/comment-quality    → reply rates, angle distribution, avg quality
GET /analytics/learning/post-quality       → post quality stats
GET /analytics/learning/scoring-calibration → score bucket engagement rates + recommendation
GET /analytics/learning/timing             → hourly/daily action counts + best hours/days
```
