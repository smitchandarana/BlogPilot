# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for BlogPilot.

Build: pyinstaller blogpilot.spec
Output: dist/BlogPilot/BlogPilot.exe

IMPORTANT: Run `cd ui && npm run build` BEFORE building the EXE.
"""

import os

block_cipher = None

# Project root (where this spec file lives)
# SPECPATH is the full path to this .spec file
ROOT = os.path.abspath(SPECPATH if os.path.isdir(SPECPATH) else os.path.dirname(SPECPATH))

a = Analysis(
    [os.path.join(ROOT, 'launcher.py')],
    pathex=[ROOT],
    binaries=[],
    datas=[
        # Bundled read-only assets
        (os.path.join(ROOT, 'config', 'settings.yaml'), os.path.join('config')),
        (os.path.join(ROOT, 'prompts'), 'prompts'),
        (os.path.join(ROOT, 'ui', 'dist'), os.path.join('ui', 'dist')),
        # Backend source (needed for uvicorn import-string "backend.main:app")
        (os.path.join(ROOT, 'backend'), 'backend'),
    ],
    hiddenimports=[
        # Uvicorn internals
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
        # SQLAlchemy dialects
        'sqlalchemy.dialects.sqlite',
        # FastAPI / Starlette
        'starlette.responses',
        'starlette.staticfiles',
        'starlette.routing',
        'starlette.middleware',
        'starlette.middleware.cors',
        # Multipart (required by FastAPI)
        'multipart',
        # Pydantic
        'pydantic',
        'pydantic_settings',
        # WebSockets
        'websockets',
        'websockets.legacy',
        'websockets.legacy.server',
        # Backend modules (ensure they're found)
        'backend',
        'backend.main',
        'backend.api',
        'backend.api.engine',
        'backend.api.config',
        'backend.api.analytics',
        'backend.api.campaigns',
        'backend.api.leads',
        'backend.api.content',
        'backend.api.websocket',
        'backend.api.server',
        'backend.core',
        'backend.core.engine',
        'backend.core.state_manager',
        'backend.core.task_queue',
        'backend.core.worker_pool',
        'backend.core.scheduler',
        'backend.core.rate_limiter',
        'backend.core.circuit_breaker',
        'backend.core.pipeline',
        'backend.storage',
        'backend.storage.database',
        'backend.storage.models',
        'backend.storage.post_state',
        'backend.storage.engagement_log',
        'backend.storage.budget_tracker',
        'backend.storage.leads_store',
        'backend.storage.quality_log',
        'backend.utils',
        'backend.utils.logger',
        'backend.utils.encryption',
        'backend.utils.config_loader',
        'backend.utils.lock_file',
        'backend.utils.paths',
        'backend.ai',
        'backend.ai.groq_client',
        'backend.ai.prompt_loader',
        'backend.ai.relevance_classifier',
        'backend.ai.comment_generator',
        'backend.ai.post_generator',
        'backend.ai.note_writer',
        'backend.ai.reply_generator',
        'backend.automation',
        'backend.automation.browser',
        'backend.automation.linkedin_login',
        'backend.automation.feed_scanner',
        'backend.automation.profile_scraper',
        'backend.automation.interaction_engine',
        'backend.automation.human_behavior',
        'backend.automation.post_publisher',
        'backend.growth',
        'backend.growth.viral_detector',
        'backend.growth.influencer_monitor',
        'backend.growth.engagement_strategy',
        'backend.growth.campaign_engine',
        'backend.growth.topic_rotator',
        'backend.enrichment',
        'backend.enrichment.email_enricher',
        'backend.enrichment.dom_email_scraper',
        'backend.enrichment.pattern_generator',
        'backend.enrichment.smtp_verifier',
        'backend.enrichment.hunter_client',
        # APScheduler
        'apscheduler.schedulers.background',
        'apscheduler.jobstores.sqlalchemy',
        'apscheduler.executors.pool',
        # Watchdog
        'watchdog.observers',
        'watchdog.events',
        # Cryptography
        'cryptography',
        'cryptography.fernet',
        # YAML
        'yaml',
        # DNS (for SMTP verifier)
        'dns',
        'dns.resolver',
        # HTTP
        'httpx',
        # Groq
        'groq',
        # Tenacity
        'tenacity',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude dev/test packages
        'pytest',
        'pytest_asyncio',
        'tkinter',
        '_tkinter',
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

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BlogPilot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # NO console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if you have one: icon='assets/icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='BlogPilot',
)
