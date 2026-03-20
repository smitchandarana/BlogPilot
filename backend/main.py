import asyncio
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
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
    # Dev: Vite on :3000. EXE: FastAPI self-serves on :8000 (same origin, but include for clarity)
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000",
                   "http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Token"],
)

# ── Authentication dependency ──────────────────────────────────────
try:
    from fastapi import Depends
    from backend.utils.auth import require_auth
    _auth = [Depends(require_auth)]
except ImportError as _auth_import_err:
    # Auth module failed to import — this means all API routes would be unprotected.
    # Fail fast rather than silently disabling auth.
    logger.critical(
        f"FATAL: auth module failed to import ({_auth_import_err}). "
        "Refusing to start with auth disabled. "
        "Check that 'cryptography' and 'fastapi' packages are installed."
    )
    sys.exit(1)

# ── Register routers ──────────────────────────────────────────────
try:
    from backend.api.engine import router as engine_router
    app.include_router(engine_router, prefix="/engine", tags=["engine"], dependencies=_auth)
except ImportError:
    pass

try:
    from backend.api.config import router as config_router
    app.include_router(config_router, prefix="", tags=["config"], dependencies=_auth)
except ImportError:
    pass

try:
    from backend.api.analytics import router as analytics_router
    app.include_router(analytics_router, prefix="/analytics", tags=["analytics"], dependencies=_auth)
except ImportError:
    pass

try:
    from backend.api.campaigns import router as campaigns_router
    app.include_router(campaigns_router, prefix="/campaigns", tags=["campaigns"], dependencies=_auth)
except ImportError:
    pass

try:
    from backend.api.leads import router as leads_router
    app.include_router(leads_router, prefix="/leads", tags=["leads"], dependencies=_auth)
except ImportError:
    pass

try:
    from backend.api.content import router as content_router
    app.include_router(content_router, prefix="/content", tags=["content"], dependencies=_auth)
except ImportError:
    pass

try:
    from backend.api.websocket import router as ws_router
    # WebSocket auth handled inside the WS connection handler
    app.include_router(ws_router, tags=["websocket"])
except ImportError:
    pass

try:
    from backend.api.server import router as server_router
    app.include_router(server_router, prefix="/server", tags=["server"], dependencies=_auth)
except ImportError:
    pass

try:
    from backend.api.research import router as research_router
    app.include_router(research_router, prefix="/research", tags=["research"], dependencies=_auth)
except ImportError:
    pass

try:
    from backend.api.intelligence import router as intelligence_router
    app.include_router(intelligence_router, prefix="/intelligence", tags=["intelligence"], dependencies=_auth)
except ImportError:
    pass


@app.get("/auth/token")
async def get_token(request: Request):
    """Return the API token ONLY for localhost clients (Settings bootstrap)."""
    client_host = request.client.host if request.client else ""
    if client_host not in ("127.0.0.1", "::1", "localhost"):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=403, content={"detail": "Forbidden"})
    try:
        from backend.utils.auth import get_api_token
        return {"token": get_api_token()}
    except Exception:
        return {"token": None}


@app.get("/health")
async def health():
    state = "UNKNOWN"
    try:
        # BUG FIX: Use the engine singleton's state_manager instead of
        # instantiating a new StateManager(), which always returns STOPPED.
        from backend.core.engine import get_engine
        eng = get_engine()
        if eng is not None:
            state = eng.state_manager.get().value
        else:
            state = "STOPPED"
    except Exception:
        state = "STOPPED"
    return {"status": "ok", "engine_state": state}


# ── Serve React frontend (EXE + production mode) ───────────────────────────────
# Mounted LAST so API routes take priority. `html=True` handles SPA client-side routing.
import os as _os
from pathlib import Path as _Path

_UI_DIST = _Path(__file__).resolve().parent.parent / "ui" / "dist"

if _UI_DIST.is_dir():
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    # Serve /assets/* directly (JS, CSS, images bundled by Vite)
    _assets = _UI_DIST / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")

    # Catch-all: serve index.html for any path not matched by API routes
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Serve real files that exist in dist (favicon, manifest, etc.)
        candidate = _UI_DIST / full_path
        if candidate.is_file():
            return FileResponse(str(candidate))
        # Default: serve index.html (SPA routing handled client-side)
        return FileResponse(str(_UI_DIST / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
