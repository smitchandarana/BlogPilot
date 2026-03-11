import asyncio
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.utils.logger import get_logger
from backend.utils.config_loader import load_config, watch as watch_config

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Boot sequence ──────────────────────────────────────────────
    logger.info("Engine booting...")

    # 1. Load config
    load_config()
    watch_config()

    # 2. Init database
    try:
        from backend.storage.database import init_db
        init_db()
        logger.info("Database initialised")
    except Exception as e:
        logger.error(f"Database init failed: {e}")

    # 3. Acquire single-instance lock
    try:
        from backend.utils.lock_file import acquire
        if not acquire():
            logger.error("Another engine instance is running. Exiting.")
            sys.exit(1)
        logger.info("Instance lock acquired")
    except Exception as e:
        logger.warning(f"Lock file error: {e}")

    # 4. Register event loop for WebSocket sync broadcasts (must happen before engine init)
    try:
        from backend.api.websocket import set_event_loop
        set_event_loop(asyncio.get_event_loop())
        logger.info("WebSocket event loop registered")
    except Exception as e:
        logger.warning(f"WebSocket event loop setup failed: {e}")

    # 5. Init engine singleton — does NOT start it; user starts via UI
    try:
        from backend.core.engine import init_engine
        app.state.engine = init_engine()
        logger.info("Engine singleton initialised (STOPPED — awaiting user start)")
    except Exception as e:
        logger.warning(f"Engine init failed: {e}")

    logger.info("Engine boot complete — listening")
    yield

    # ── Shutdown sequence ──────────────────────────────────────────
    logger.info("Engine shutting down...")

    # Stop engine gracefully if it was started
    try:
        from backend.core.engine import get_engine
        from backend.core.state_manager import EngineState
        eng = get_engine()
        if eng and eng.state_manager.get() != EngineState.STOPPED:
            eng.stop()
    except Exception:
        pass

    try:
        from backend.utils.lock_file import release
        release()
    except Exception:
        pass

    try:
        from backend.utils.config_loader import stop_watch
        stop_watch()
    except Exception:
        pass

    logger.info("Engine shutdown complete")  # Sprint 6


app = FastAPI(
    title="LinkedIn AI Growth Engine",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ──────────────────────────────────────────────
try:
    from backend.api.engine import router as engine_router
    app.include_router(engine_router, prefix="/engine", tags=["engine"])
except ImportError:
    pass

try:
    from backend.api.config import router as config_router
    app.include_router(config_router, prefix="", tags=["config"])
except ImportError:
    pass

try:
    from backend.api.analytics import router as analytics_router
    app.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
except ImportError:
    pass

try:
    from backend.api.campaigns import router as campaigns_router
    app.include_router(campaigns_router, prefix="/campaigns", tags=["campaigns"])
except ImportError:
    pass

try:
    from backend.api.leads import router as leads_router
    app.include_router(leads_router, prefix="/leads", tags=["leads"])
except ImportError:
    pass

try:
    from backend.api.content import router as content_router
    app.include_router(content_router, prefix="/content", tags=["content"])
except ImportError:
    pass

try:
    from backend.api.websocket import router as ws_router
    app.include_router(ws_router, tags=["websocket"])
except ImportError:
    pass


@app.get("/health")
async def health():
    state = "UNKNOWN"
    try:
        from backend.core.state_manager import StateManager
        state = StateManager().get().value
    except Exception:
        state = "STOPPED"
    return {"status": "ok", "engine_state": state}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
