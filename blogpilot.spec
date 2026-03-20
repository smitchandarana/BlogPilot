# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for BlogPilot.

Build steps:
    1. cd ui && npm run build
    2. pyinstaller blogpilot.spec

Output: dist/BlogPilot/BlogPilot.exe

To create the installer (requires Inno Setup 6):
    iscc installer.iss
"""

import os

block_cipher = None

ROOT = os.path.abspath(SPECPATH if os.path.isdir(SPECPATH) else os.path.dirname(SPECPATH))

a = Analysis(
    [os.path.join(ROOT, 'launcher.py')],
    pathex=[ROOT],
    binaries=[],
    datas=[
        # Config + prompts (read-only defaults bundled with the EXE)
        (os.path.join(ROOT, 'config', 'settings.yaml'), os.path.join('config')),
        (os.path.join(ROOT, 'prompts'), 'prompts'),
        # Built React frontend (Vite output — run `cd ui && npm run build` first)
        (os.path.join(ROOT, 'ui', 'dist'), os.path.join('ui', 'dist')),
        # Backend source (needed so uvicorn can import "backend.main:app")
        (os.path.join(ROOT, 'backend'), 'backend'),
    ],
    hiddenimports=[
        # ── Uvicorn internals ──────────────────────────────────────
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.protocols.websockets.websockets_impl',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'uvicorn.lifespan.off',
        # ── SQLAlchemy ─────────────────────────────────────────────
        'sqlalchemy.dialects.sqlite',
        'sqlalchemy.dialects.sqlite.pysqlite',
        # ── FastAPI / Starlette ────────────────────────────────────
        'starlette.responses',
        'starlette.staticfiles',
        'starlette.routing',
        'starlette.middleware',
        'starlette.middleware.cors',
        # ── Multipart / Pydantic ───────────────────────────────────
        'multipart',
        'pydantic',
        'pydantic_settings',
        # ── WebSockets ─────────────────────────────────────────────
        'websockets',
        'websockets.legacy',
        'websockets.legacy.server',
        # ── Backend: main ──────────────────────────────────────────
        'backend',
        'backend.main',
        # ── Backend: API layer ─────────────────────────────────────
        'backend.api',
        'backend.api.engine',
        'backend.api.config',
        'backend.api.analytics',
        'backend.api.campaigns',
        'backend.api.leads',
        'backend.api.content',
        'backend.api.websocket',
        'backend.api.server',
        'backend.api.research',
        'backend.api.intelligence',
        # ── Backend: core engine ───────────────────────────────────
        'backend.core',
        'backend.core.engine',
        'backend.core.state_manager',
        'backend.core.task_queue',
        'backend.core.worker_pool',
        'backend.core.scheduler',
        'backend.core.rate_limiter',
        'backend.core.circuit_breaker',
        'backend.core.pipeline',
        # ── Backend: storage ───────────────────────────────────────
        'backend.storage',
        'backend.storage.database',
        'backend.storage.models',
        'backend.storage.post_state',
        'backend.storage.engagement_log',
        'backend.storage.budget_tracker',
        'backend.storage.leads_store',
        'backend.storage.quality_log',
        # ── Backend: utils ─────────────────────────────────────────
        'backend.utils',
        'backend.utils.logger',
        'backend.utils.encryption',
        'backend.utils.config_loader',
        'backend.utils.lock_file',
        'backend.utils.paths',
        'backend.utils.auth',
        # ── Backend: AI layer ──────────────────────────────────────
        'backend.ai',
        'backend.ai.groq_client',
        'backend.ai.openrouter_client',
        'backend.ai.client_factory',
        'backend.ai.utils',
        'backend.ai.prompt_loader',
        'backend.ai.relevance_classifier',
        'backend.ai.comment_generator',
        'backend.ai.post_generator',
        'backend.ai.note_writer',
        'backend.ai.reply_generator',
        # ── Backend: automation ────────────────────────────────────
        'backend.automation',
        'backend.automation.browser',
        'backend.automation.linkedin_login',
        'backend.automation.feed_scanner',
        'backend.automation.profile_scraper',
        'backend.automation.interaction_engine',
        'backend.automation.human_behavior',
        'backend.automation.post_publisher',
        'backend.automation.hashtag_scanner',
        # ── Backend: growth ────────────────────────────────────────
        'backend.growth',
        'backend.growth.viral_detector',
        'backend.growth.influencer_monitor',
        'backend.growth.engagement_strategy',
        'backend.growth.campaign_engine',
        'backend.growth.topic_rotator',
        # ── Backend: enrichment ────────────────────────────────────
        'backend.enrichment',
        'backend.enrichment.email_enricher',
        'backend.enrichment.dom_email_scraper',
        'backend.enrichment.pattern_generator',
        'backend.enrichment.smtp_verifier',
        'backend.enrichment.hunter_client',
        # ── Backend: research ──────────────────────────────────────
        'backend.research',
        'backend.research.topic_researcher',
        'backend.research.reddit_scanner',
        'backend.research.rss_scanner',
        'backend.research.hn_scanner',
        'backend.research.linkedin_insights',
        'backend.research.duplicate_detector',
        'backend.research.content_extractor',
        'backend.research.pattern_aggregator',
        # ── Backend: learning ──────────────────────────────────────
        'backend.learning',
        'backend.learning.comment_monitor',
        'backend.learning.scoring_calibrator',
        'backend.learning.timing_analyzer',
        'backend.learning.auto_tuner',
        'backend.learning.content_preference_learner',
        # ── APScheduler ───────────────────────────────────────────
        'apscheduler',
        'apscheduler.schedulers.background',
        'apscheduler.jobstores.sqlalchemy',
        'apscheduler.executors.pool',
        'apscheduler.triggers.interval',
        'apscheduler.triggers.cron',
        # ── Watchdog ───────────────────────────────────────────────
        'watchdog.observers',
        'watchdog.events',
        'watchdog.observers.polling',
        # ── Cryptography ───────────────────────────────────────────
        'cryptography',
        'cryptography.fernet',
        'cryptography.hazmat',
        'cryptography.hazmat.primitives',
        'cryptography.hazmat.backends',
        # ── YAML ───────────────────────────────────────────────────
        'yaml',
        # ── Networking / DNS ───────────────────────────────────────
        'dns',
        'dns.resolver',
        'httpx',
        # ── AI providers ───────────────────────────────────────────
        'groq',
        'openai',           # OpenRouter uses the openai SDK
        'tenacity',
        # ── Feed parsing ───────────────────────────────────────────
        'feedparser',
        # ── Playwright (bundled separately; just ensure hooks load) ─
        'playwright',
        'playwright.sync_api',
        'playwright.async_api',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest',
        'pytest_asyncio',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'cv2',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# --onefile: everything bundled into a single EXE that self-extracts to %TEMP% at launch.
# This means the user only needs one file — no _internal/ folder required.
# Startup takes ~3–5 seconds on first run while it extracts; faster on subsequent runs
# if the OS caches the temp files.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,     # bundle binaries directly into the EXE (onefile mode)
    a.datas,        # bundle data files directly into the EXE (onefile mode)
    name='BlogPilot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # No console window shown to end users
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # Add: icon='assets/icon.ico'
)
