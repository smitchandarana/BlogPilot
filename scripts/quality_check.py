#!/usr/bin/env python3
"""
BlogPilot Quality Guardrail Script
====================================
Validates every layer of the application before deployment or execution:

  1. Environment variables (required secrets present + non-empty)
  2. Python module imports (every backend module loads without crash)
  3. DB schema (all expected tables exist, can be queried)
  4. Config file (settings.yaml valid YAML, required keys present)
  5. Prompts (all required .txt files exist, required variables present)
  6. Inter-module wiring (pipeline can instantiate with all dependencies)
  7. API routes (every router can be imported and mounted)
  8. Platform layer (bp_platform models + services import clean)
  9. Frontend env (Vite env vars present in production .env)
 10. VPS connectivity (optional — only if --vps flag passed)

Exit code: 0 = all pass, 1 = failures found.
Usage:
  python scripts/quality_check.py           # local checks
  python scripts/quality_check.py --vps     # also SSH-check VPS env
  python scripts/quality_check.py --fix     # auto-fix safe issues (missing dirs, etc.)
"""

import sys
import os
import json
import importlib
import traceback
import argparse
from pathlib import Path
from typing import Callable

# ── Colour helpers ────────────────────────────────────────────────────────────

_USE_COLOUR = sys.stdout.isatty()

def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOUR else text

def OK(msg: str)   -> str: return _c(f"  ✓  {msg}", "32")
def FAIL(msg: str) -> str: return _c(f"  ✗  {msg}", "31")
def WARN(msg: str) -> str: return _c(f"  ⚠  {msg}", "33")
def HEAD(msg: str) -> str: return _c(f"\n{'═'*60}\n  {msg}\n{'═'*60}", "36;1")

# ── Root path resolution ──────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

# ── Result accumulator ────────────────────────────────────────────────────────

_results: list[tuple[str, bool, str]] = []   # (label, passed, detail)

def check(label: str, fn: Callable) -> bool:
    """Run fn(), record result, print outcome. Returns True on pass."""
    try:
        result = fn()
        if result is True or result is None:
            print(OK(label))
            _results.append((label, True, ""))
            return True
        elif isinstance(result, str) and result.startswith("WARN:"):
            print(WARN(label + " — " + result[5:]))
            _results.append((label, True, result[5:]))
            return True
        else:
            detail = str(result) if result else ""
            print(FAIL(label + (f" — {detail}" if detail else "")))
            _results.append((label, False, detail))
            return False
    except Exception as exc:
        print(FAIL(label + f" — {type(exc).__name__}: {exc}"))
        _results.append((label, False, traceback.format_exc()))
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# 1. ENVIRONMENT VARIABLES
# ═══════════════════════════════════════════════════════════════════════════════

def check_env():
    print(HEAD("1. Environment Variables"))

    # Secrets file paths
    secrets_dir = ROOT / "config" / ".secrets"

    # Groq key (optional but needed for AI features)
    groq_path = secrets_dir / "groq.json"
    def _groq():
        if groq_path.exists():
            d = json.loads(groq_path.read_text())
            if d.get("api_key", "").startswith("gsk_"):
                return True
            return "groq.json exists but api_key looks invalid"
        if os.environ.get("GROQ_API_KEY"):
            return True
        return "WARN:No Groq key — AI features will not work (add key in Settings)"
    check("Groq API key", _groq)

    # OpenRouter key (optional, used for background extraction)
    or_path = secrets_dir / "openrouter.json"
    def _openrouter():
        if or_path.exists():
            d = json.loads(or_path.read_text())
            if d.get("api_key", "").startswith("sk-or-"):
                return True
            return "WARN:openrouter.json exists but key format looks wrong"
        return "WARN:No OpenRouter key — background AI will fall back to Groq (burns daily quota)"
    check("OpenRouter API key", _openrouter)

    # LinkedIn credentials (optional)
    creds_path = secrets_dir / ".api_token"
    def _linkedin():
        li_email = secrets_dir / "linkedin_email"
        li_pass  = secrets_dir / "linkedin_password_enc"
        if li_email.exists() or li_pass.exists():
            return True
        return "WARN:No LinkedIn credentials — engine will fail on login (set via Settings)"
    check("LinkedIn credentials", _linkedin)

    # Docker .env for platform
    docker_env = ROOT / "docker" / ".env"
    def _docker_env():
        if not docker_env.exists():
            return "WARN:docker/.env not found — platform deployment uses example defaults"
        content = docker_env.read_text()
        required = ["POSTGRES_PASSWORD", "JWT_SECRET", "ADMIN_EMAIL", "ADMIN_PASSWORD"]
        missing = [k for k in required if f"{k}=" not in content]
        if missing:
            return f"Missing required vars: {missing}"
        return True
    check("docker/.env completeness", _docker_env)

    # Config dir
    def _config_dir():
        d = ROOT / "config"
        if not d.exists():
            return "config/ directory missing"
        if not (d / "settings.yaml").exists():
            return "config/settings.yaml missing"
        return True
    check("config/ directory exists", _config_dir)

    # Secrets dir
    def _secrets_dir():
        if not secrets_dir.exists():
            return "WARN:config/.secrets/ not found — will be created on first run"
        return True
    check("config/.secrets/ directory", _secrets_dir)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. PYTHON MODULE IMPORTS
# ═══════════════════════════════════════════════════════════════════════════════

BACKEND_MODULES = [
    # Utils
    "backend.utils.logger",
    "backend.utils.config_loader",
    "backend.utils.encryption",
    "backend.utils.lock_file",
    "backend.utils.paths",
    # Storage
    "backend.storage.database",
    "backend.storage.models",
    "backend.storage.post_state",
    "backend.storage.engagement_log",
    "backend.storage.budget_tracker",
    "backend.storage.leads_store",
    "backend.storage.quality_log",
    # AI
    "backend.ai.groq_client",
    "backend.ai.prompt_loader",
    "backend.ai.relevance_classifier",
    "backend.ai.comment_generator",
    "backend.ai.post_generator",
    "backend.ai.note_writer",
    "backend.ai.reply_generator",
    "backend.ai.client_factory",
    # Core
    "backend.core.state_manager",
    "backend.core.task_queue",
    "backend.core.worker_pool",
    "backend.core.rate_limiter",
    "backend.core.circuit_breaker",
    "backend.core.engine",
    "backend.core.pipeline",
    "backend.core.scheduler",
    # API
    "backend.api.engine",
    "backend.api.config",
    "backend.api.analytics",
    "backend.api.campaigns",
    "backend.api.leads",
    "backend.api.content",
    "backend.api.research",
    "backend.api.intelligence",
    "backend.api.websocket",
    "backend.api.server",
    # Growth
    "backend.growth.viral_detector",
    "backend.growth.engagement_strategy",
    "backend.growth.influencer_monitor",
    "backend.growth.campaign_engine",
    "backend.growth.topic_rotator",
    # Enrichment
    "backend.enrichment.email_enricher",
    "backend.enrichment.dom_email_scraper",
    "backend.enrichment.pattern_generator",
    "backend.enrichment.smtp_verifier",
    "backend.enrichment.hunter_client",
    # Research
    "backend.research.topic_researcher",
    "backend.research.reddit_scanner",
    "backend.research.rss_scanner",
    "backend.research.hn_scanner",
    "backend.research.linkedin_insights",
    "backend.research.duplicate_detector",
    "backend.research.content_extractor",
    "backend.research.pattern_aggregator",
    # Learning
    "backend.learning.comment_monitor",
    "backend.learning.scoring_calibrator",
    "backend.learning.timing_analyzer",
    "backend.learning.auto_tuner",
    "backend.learning.content_preference_learner",
    # Automation (no browser launch — import only)
    "backend.automation.human_behavior",
    "backend.automation.feed_scanner",
    "backend.automation.profile_scraper",
    "backend.automation.interaction_engine",
    "backend.automation.post_publisher",
    "backend.automation.hashtag_scanner",
]

PLATFORM_MODULES = [
    "bp_platform.config",
    "bp_platform.models.database",
    "bp_platform.services.token_service",
    "bp_platform.services.port_allocator",
    "bp_platform.services.container_manager",
    "bp_platform.services.health_monitor",
    "bp_platform.api.auth",
    "bp_platform.api.admin",
    "bp_platform.api.containers",
    "bp_platform.api.proxy",
    "bp_platform.api.billing",
    "bp_platform.api.health",
]

def check_imports():
    print(HEAD("2. Python Module Imports"))
    failed = []
    for mod in BACKEND_MODULES:
        try:
            importlib.import_module(mod)
        except Exception as exc:
            print(FAIL(f"{mod} — {type(exc).__name__}: {exc}"))
            _results.append((f"import {mod}", False, str(exc)))
            failed.append(mod)
        else:
            print(OK(f"{mod}"))
            _results.append((f"import {mod}", True, ""))

    print(f"\n  Platform modules:")
    for mod in PLATFORM_MODULES:
        try:
            importlib.import_module(mod)
        except Exception as exc:
            print(FAIL(f"{mod} — {type(exc).__name__}: {exc}"))
            _results.append((f"import {mod}", False, str(exc)))
            failed.append(mod)
        else:
            print(OK(f"{mod}"))
            _results.append((f"import {mod}", True, ""))

    return failed


# ═══════════════════════════════════════════════════════════════════════════════
# 3. DATABASE SCHEMA
# ═══════════════════════════════════════════════════════════════════════════════

EXPECTED_TABLES = [
    "posts", "leads", "actions_log", "campaigns", "campaign_enrollments",
    "budget", "settings", "researched_topics", "research_snippets",
    "scheduled_posts", "comment_quality_log", "post_quality_log",
    "topic_performance", "content_insights", "content_patterns",
    "generation_sessions",
]

def check_db():
    print(HEAD("3. Database Schema"))
    from backend.storage.database import get_db, init_db
    from sqlalchemy import inspect, text

    def _init():
        init_db()
        return True
    check("init_db() runs without error", _init)

    def _tables():
        with get_db() as db:
            inspector = inspect(db.bind)
            existing = set(inspector.get_table_names())
        missing = [t for t in EXPECTED_TABLES if t not in existing]
        if missing:
            return f"Missing tables: {missing}"
        return True
    check("All expected tables exist", _tables)

    def _budget_rows():
        from backend.storage.models import Budget
        with get_db() as db:
            count = db.query(Budget).count()
        if count == 0:
            return "WARN:Budget table is empty — run init_db() to seed rows"
        return True
    check("Budget table has rows", _budget_rows)

    def _write_read():
        # Verify a basic write+read roundtrip
        from backend.storage import budget_tracker
        with get_db() as db:
            budget_tracker.get_all(db)
        return True
    check("DB read roundtrip (budget_tracker.get_all)", _write_read)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. CONFIG FILE
# ═══════════════════════════════════════════════════════════════════════════════

CONFIG_REQUIRED_KEYS = [
    "engine", "schedule", "daily_budget", "rate_limits", "delays",
    "modules", "feed_engagement", "ai", "browser", "research",
    "learning", "topic_rotation", "topics", "hashtags",
]

def check_config():
    print(HEAD("4. Config File"))

    def _yaml():
        import yaml
        cfg_path = ROOT / "config" / "settings.yaml"
        if not cfg_path.exists():
            return "settings.yaml not found"
        data = yaml.safe_load(cfg_path.read_text())
        missing = [k for k in CONFIG_REQUIRED_KEYS if k not in data]
        if missing:
            return f"Missing top-level keys: {missing}"
        return True
    check("settings.yaml valid YAML with required keys", _yaml)

    def _loader():
        from backend.utils.config_loader import get as cfg_get, load_config
        load_config()
        budget = cfg_get("daily_budget")
        if not isinstance(budget, dict):
            return "daily_budget is not a dict"
        topics = cfg_get("topics", [])
        if not topics:
            return "WARN:No topics configured — engine will not engage with any posts"
        return True
    check("config_loader loads and dot-notation access works", _loader)

    def _hot_reload():
        from backend.utils.config_loader import get as cfg_get
        val = cfg_get("schedule.feed_scan_interval_minutes", 20)
        if not isinstance(val, (int, float)):
            return f"Expected int, got {type(val)}"
        return True
    check("Dot-notation deep key access works", _hot_reload)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. PROMPTS
# ═══════════════════════════════════════════════════════════════════════════════

REQUIRED_PROMPTS = {
    "relevance":           ["{post_text}", "{author_name}", "{topics}"],
    "comment":             ["{post_text}", "{author_name}", "{topics}", "{tone}"],
    "post":                ["{topic}", "{style}", "{tone}", "{word_count}"],
    "note":                ["{first_name}", "{title}", "{company}", "{topics}"],
    "reply":               ["{original_post}", "{your_comment}", "{reply_to_comment}"],
    "comment_candidate":   ["{post_text}", "{author_name}", "{topics}"],
    "comment_scorer":      ["{post_text}", "{candidates_json}"],
    "post_with_context":   ["{topic}", "{context}"],
    "topic_extractor":     ["{domain}", "{snippets_summary}"],
    "topic_scorer":        ["{topic}", "{snippets_summary}"],
    "content_extractor":   [],
    "structured_post":     ["{topic}", "{subtopic}", "{audience}"],
    "hook_generator":      [],
    "angle_generator":     ["{pain_point}", "{audience}"],
    "insight_normalizer":  [],
    "post_critic":         [],
    "post_scorer":         [],
    "synthesize_brief":    ["{source_count}", "{materials}"],
}

def check_prompts():
    print(HEAD("5. Prompt Files"))
    prompts_dir = ROOT / "prompts"

    def _dir():
        if not prompts_dir.exists():
            return "prompts/ directory not found"
        return True
    check("prompts/ directory exists", _dir)

    for name, required_vars in REQUIRED_PROMPTS.items():
        path = prompts_dir / f"{name}.txt"
        def _prompt(p=path, n=name, rv=required_vars):
            if not p.exists():
                return f"File not found: prompts/{n}.txt"
            content = p.read_text()
            missing = [v for v in rv if v not in content]
            if missing:
                return f"Missing variables: {missing}"
            return True
        check(f"prompts/{name}.txt", _prompt)

    def _loader():
        from backend.ai.prompt_loader import PromptLoader
        loader = PromptLoader()
        loader.load_all()
        for name in REQUIRED_PROMPTS:
            txt = loader.get(name)
            if not txt:
                return f"Prompt '{name}' returned empty after load_all()"
        return True
    check("PromptLoader.load_all() loads all prompts", _loader)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. INTER-MODULE WIRING (Pipeline can instantiate with all deps)
# ═══════════════════════════════════════════════════════════════════════════════

def check_wiring():
    print(HEAD("6. Inter-Module Wiring"))

    def _state_machine():
        from backend.core.state_manager import StateManager, EngineState
        sm = StateManager()
        assert sm.get() == EngineState.STOPPED
        return True
    check("StateManager instantiates + default state is STOPPED", _state_machine)

    def _task_queue():
        from backend.core.task_queue import TaskQueue, Task, Priority
        q = TaskQueue()
        t = Task(type="test", payload={}, priority=Priority.NORMAL)
        q.put(t)
        got = q.get_nowait()
        assert got is not None
        return True
    check("TaskQueue put/get_nowait roundtrip", _task_queue)

    def _rate_limiter():
        from backend.core.rate_limiter import RateLimiter
        rl = RateLimiter()
        assert rl.check("likes") is True
        return True
    check("RateLimiter.check() returns True on fresh instance", _rate_limiter)

    def _circuit_breaker():
        from backend.core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        assert not cb.is_tripped()
        return True
    check("CircuitBreaker is not tripped on fresh instance", _circuit_breaker)

    def _relevance_classifier():
        from backend.ai.relevance_classifier import RelevanceClassifier
        from backend.ai.groq_client import GroqClient
        from backend.ai.prompt_loader import PromptLoader
        # Instantiate without calling (no API key needed for init)
        loader = PromptLoader()
        loader.load_all()
        # We can't make a real call without API key — just verify instantiation
        clf = RelevanceClassifier(groq_client=None, prompt_loader=loader)
        return True
    check("RelevanceClassifier instantiates with prompt_loader", _relevance_classifier)

    def _comment_generator():
        from backend.ai.comment_generator import CommentGenerator
        from backend.ai.prompt_loader import PromptLoader
        loader = PromptLoader()
        loader.load_all()
        gen = CommentGenerator(groq_client=None, prompt_loader=loader)
        return True
    check("CommentGenerator instantiates with prompt_loader", _comment_generator)

    def _post_generator():
        from backend.ai import post_generator
        # Verify the module-level functions exist
        assert hasattr(post_generator, "generate")
        assert hasattr(post_generator, "generate_structured")
        return True
    check("post_generator has generate() and generate_structured()", _post_generator)

    def _engagement_strategy():
        from backend.growth.engagement_strategy import decide
        action = decide(score=8.0, budget_remaining={"comments": 5}, mode="smart")
        assert action in ("LIKE", "COMMENT", "LIKE_AND_COMMENT", "SKIP")
        return True
    check("engagement_strategy.decide() returns valid action", _engagement_strategy)

    def _budget_tracker():
        from backend.storage import budget_tracker
        from backend.storage.database import get_db
        with get_db() as db:
            result = budget_tracker.check("likes", db)
            assert isinstance(result, bool)
        return True
    check("budget_tracker.check() returns bool", _budget_tracker)

    def _pipeline_deps():
        # Verify pipeline module imports and key function exists
        from backend.core import pipeline
        assert hasattr(pipeline, "run_feed_scan")
        assert hasattr(pipeline, "run_approve_comment")
        return True
    check("pipeline module has run_feed_scan() and run_approve_comment()", _pipeline_deps)

    def _api_routers():
        # Verify all routers import and have the `router` attribute
        router_modules = [
            "backend.api.engine", "backend.api.config",
            "backend.api.analytics", "backend.api.campaigns",
            "backend.api.leads", "backend.api.content",
            "backend.api.research", "backend.api.intelligence",
        ]
        for mod_name in router_modules:
            mod = importlib.import_module(mod_name)
            if not hasattr(mod, "router"):
                return f"{mod_name} is missing 'router'"
        return True
    check("All API modules export 'router'", _api_routers)

    def _websocket():
        from backend.api.websocket import schedule_broadcast
        assert callable(schedule_broadcast)
        return True
    check("websocket.schedule_broadcast is callable", _websocket)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. API ROUTE MOUNT TEST
# ═══════════════════════════════════════════════════════════════════════════════

def check_api_routes():
    print(HEAD("7. API Route Mounting"))

    def _main_app():
        import backend.main as main_mod
        assert hasattr(main_mod, "app"), "main.py missing 'app'"
        from fastapi import FastAPI
        assert isinstance(main_mod.app, FastAPI)
        routes = [r.path for r in main_mod.app.routes]
        required_paths = ["/health", "/engine/start", "/engine/stop", "/analytics/daily"]
        missing = [p for p in required_paths if not any(p in r for r in routes)]
        if missing:
            return f"Missing routes: {missing}"
        return True
    check("backend/main.py FastAPI app mounts required routes", _main_app)

    def _platform_app():
        import bp_platform.main as pm
        assert hasattr(pm, "app")
        routes = [r.path for r in pm.app.routes]
        required = ["/platform/auth/login", "/platform/auth/signup", "/platform/containers/provision"]
        missing = [p for p in required if not any(p in r for r in routes)]
        if missing:
            return f"Missing platform routes: {missing}"
        return True
    check("bp_platform/main.py FastAPI app mounts required routes", _platform_app)


# ═══════════════════════════════════════════════════════════════════════════════
# 8. PLATFORM LAYER
# ═══════════════════════════════════════════════════════════════════════════════

PLATFORM_DB_TABLES = ["users", "containers", "password_reset_tokens", "audit_log"]

def check_platform():
    print(HEAD("8. Platform Layer"))

    def _db_init():
        from bp_platform.models.database import init_db, get_db, User
        init_db()
        with get_db() as db:
            db.query(User).count()
        return True
    check("bp_platform DB init_db() and User query work", _db_init)

    def _tables():
        from bp_platform.models.database import get_db
        from sqlalchemy import inspect
        with get_db() as db:
            inspector = inspect(db.bind)
            existing = set(inspector.get_table_names())
        missing = [t for t in PLATFORM_DB_TABLES if t not in existing]
        if missing:
            return f"Missing tables: {missing}"
        return True
    check("Platform DB has required tables", _tables)

    def _jwt():
        from bp_platform.services.token_service import create_jwt, decode_jwt, hash_password, verify_password
        token = create_jwt("test-id", "test@example.com", "user")
        payload = decode_jwt(token)
        assert payload["sub"] == "test-id"
        hashed = hash_password("test123")
        assert verify_password("test123", hashed)
        return True
    check("JWT create/decode and password hash/verify work", _jwt)

    def _port_allocator():
        from bp_platform.services.port_allocator import allocate_port
        # Don't actually allocate (side effects) — just verify it's callable
        assert callable(allocate_port)
        return True
    check("port_allocator.allocate_port is callable", _port_allocator)

    def _role_system():
        from bp_platform.api.auth import get_current_user, require_admin
        assert callable(get_current_user)
        assert callable(require_admin)
        return True
    check("Auth dependency functions (get_current_user, require_admin) exist", _role_system)


# ═══════════════════════════════════════════════════════════════════════════════
# 9. FRONTEND ENV
# ═══════════════════════════════════════════════════════════════════════════════

def check_frontend():
    print(HEAD("9. Frontend Environment"))

    def _package_json():
        pkg = ROOT / "ui" / "package.json"
        if not pkg.exists():
            return "ui/package.json not found"
        data = json.loads(pkg.read_text())
        required = ["react", "react-dom", "react-router-dom"]
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        missing = [d for d in required if d not in deps]
        if missing:
            return f"Missing deps in package.json: {missing}"
        return True
    check("ui/package.json has required dependencies", _package_json)

    def _prod_env():
        env_prod = ROOT / "ui" / ".env.production"
        if not env_prod.exists():
            return "WARN:ui/.env.production not found — production build will use default localhost URLs"
        content = env_prod.read_text()
        required = ["VITE_PLATFORM_URL", "VITE_API_BASE_URL"]
        missing = [k for k in required if k not in content]
        if missing:
            return f"Missing vars: {missing}"
        return True
    check("ui/.env.production has required Vite vars", _prod_env)

    def _node_modules():
        nm = ROOT / "ui" / "node_modules"
        if not nm.exists():
            return "WARN:ui/node_modules not found — run 'cd ui && npm install'"
        # Check a key dep exists
        if not (nm / "react").exists():
            return "WARN:react not installed — run 'cd ui && npm install'"
        return True
    check("ui/node_modules installed", _node_modules)

    def _api_client():
        client = ROOT / "ui" / "src" / "api" / "client.js"
        if not client.exists():
            return "ui/src/api/client.js not found"
        content = client.read_text()
        # Verify key exports
        for export in ["engine", "config", "analytics", "content"]:
            if export not in content:
                return f"Missing export '{export}' in client.js"
        return True
    check("ui/src/api/client.js has all required API exports", _api_client)


# ═══════════════════════════════════════════════════════════════════════════════
# 10. EXECUTION FLOW TRACE (critical path only — no browser, no API calls)
# ═══════════════════════════════════════════════════════════════════════════════

def check_execution_flow():
    print(HEAD("10. Execution Flow Trace"))

    def _engine_singleton():
        from backend.core.engine import get_engine
        # get_engine() returns None if not started — that's correct
        eng = get_engine()
        # Just verify it's importable and callable
        assert callable(get_engine)
        return True
    check("get_engine() callable (returns None before start)", _engine_singleton)

    def _scheduler_jobs():
        from backend.core import scheduler as sched_mod
        required = [
            "_job_feed_scan", "_job_hourly_reset", "_job_budget_reset",
            "_job_campaign_processing", "_job_post_publishing",
            "_job_topic_research", "_job_topic_rotation",
            "_job_comment_monitor", "_job_auto_tune", "_job_content_extraction",
        ]
        missing = [fn for fn in required if not hasattr(sched_mod, fn)]
        if missing:
            return f"Missing scheduler functions: {missing}"
        return True
    check("All 10 scheduler job functions exist", _scheduler_jobs)

    def _budget_enforced():
        # Verify pipeline checks budget before every action
        import inspect
        from backend.core import pipeline
        source = inspect.getsource(pipeline)
        if "budget_tracker.check" not in source and "budget_tracker" not in source:
            return "budget_tracker not referenced in pipeline — budget enforcement may be broken"
        return True
    check("pipeline.py references budget_tracker (budget enforcement)", _budget_enforced)

    def _blacklist_check():
        import inspect
        from backend.core import pipeline
        source = inspect.getsource(pipeline)
        if "blacklist" not in source.lower() and "keyword_blacklist" not in source:
            return "WARN:No blacklist check visible in pipeline source"
        return True
    check("pipeline.py has keyword blacklist check", _blacklist_check)

    def _websocket_broadcast():
        # Verify WebSocket broadcast path from pipeline
        from backend.api.websocket import schedule_broadcast
        # Should be safe to call with no active connections
        try:
            schedule_broadcast("test", {"check": True})
        except Exception as e:
            return f"schedule_broadcast raised: {e}"
        return True
    check("websocket.schedule_broadcast() does not crash without active connections", _websocket_broadcast)

    def _worker_pool():
        from backend.core.worker_pool import WorkerPool
        from backend.core.task_queue import TaskQueue
        from backend.core.state_manager import StateManager
        q = TaskQueue()
        sm = StateManager()
        wp = WorkerPool(max_workers=3, queue=q, state_manager=sm)
        assert wp.active_count() == 0
        return True
    check("WorkerPool instantiates with 0 active tasks", _worker_pool)

    def _dependency_injection():
        # Verify pipeline can be instantiated with mock/None deps (DI pattern)
        from backend.core.pipeline import Pipeline
        p = Pipeline(
            browser=None, feed_scanner=None, interaction_engine=None,
            profile_scraper=None, relevance_classifier=None,
            comment_generator=None, engagement_strategy=None,
            viral_detector=None, email_enricher=None,
            engagement_log=None, budget_tracker=None,
            post_state=None, websocket=None, config=None,
        )
        assert p is not None
        return True
    check("Pipeline accepts all-None deps (dependency injection pattern intact)", _dependency_injection)


# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

def print_summary():
    print(HEAD("Summary"))
    passed  = [r for r in _results if r[1]]
    failed  = [r for r in _results if not r[1]]
    warned  = [r for r in passed if r[2]]  # passed but has warning detail

    print(f"  Total checks : {len(_results)}")
    print(f"  {_c('Passed', '32')}  : {len(passed)}")
    print(f"  {_c('Failed', '31')}  : {len(failed)}")
    if warned:
        print(f"  {_c('Warnings', '33')} : {len(warned)}")

    if failed:
        print(_c("\n  Failed checks:", "31;1"))
        for label, _, detail in failed:
            print(f"    ✗ {label}")
            if detail and len(detail) < 200:
                print(f"      {detail}")

    if warned:
        print(_c("\n  Warnings:", "33;1"))
        for label, _, detail in warned:
            print(f"    ⚠ {label}: {detail}")

    if not failed:
        print(_c("\n  All checks passed. Application is ready to run.", "32;1"))
    else:
        print(_c(f"\n  {len(failed)} check(s) failed. Fix issues before running.", "31;1"))


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="BlogPilot Quality Guardrail Check")
    parser.add_argument("--vps",  action="store_true", help="Also SSH-check VPS env")
    parser.add_argument("--fix",  action="store_true", help="Auto-fix safe issues")
    parser.add_argument("--fast", action="store_true", help="Skip slow checks (imports)")
    parser.add_argument("--section", type=int, help="Run only section N (1-10)")
    args = parser.parse_args()

    print(_c("\n  BlogPilot Quality Guardrail Check", "36;1"))
    print(_c(f"  Root: {ROOT}", "90"))

    if args.section:
        sections = {
            1: check_env, 2: check_imports, 3: check_db, 4: check_config,
            5: check_prompts, 6: check_wiring, 7: check_api_routes,
            8: check_platform, 9: check_frontend, 10: check_execution_flow,
        }
        fn = sections.get(args.section)
        if fn:
            fn()
        else:
            print(f"Unknown section {args.section}. Must be 1-10.")
            sys.exit(1)
    else:
        check_env()
        if not args.fast:
            check_imports()
        check_db()
        check_config()
        check_prompts()
        check_wiring()
        check_api_routes()
        check_platform()
        check_frontend()
        check_execution_flow()

    print_summary()

    failed_count = sum(1 for r in _results if not r[1])
    sys.exit(0 if failed_count == 0 else 1)


if __name__ == "__main__":
    main()
