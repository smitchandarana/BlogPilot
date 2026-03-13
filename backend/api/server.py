"""
Server-level process control endpoints.
Restart / shutdown the entire backend (uvicorn) process from the UI.
"""

import os
import subprocess
import sys
import time
import threading
import platform

from fastapi import APIRouter

from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

_server_start_time = time.time()


def _graceful_engine_stop():
    """Stop the engine if it's running — reused by restart and shutdown."""
    try:
        from backend.core.engine import get_engine
        from backend.core.state_manager import EngineState

        eng = get_engine()
        if eng and eng.state_manager.get() != EngineState.STOPPED:
            eng.stop()
            logger.info("Server: engine stopped before process control action")
    except Exception as exc:
        logger.warning(f"Server: engine stop during shutdown failed: {exc}")


def _release_lock():
    """Release instance lock file."""
    try:
        from backend.utils.lock_file import release
        release()
    except Exception:
        pass


@router.get("/info")
async def server_info():
    """Return server process info: PID, uptime, python version, start time."""
    return {
        "pid": os.getpid(),
        "uptime_seconds": int(time.time() - _server_start_time),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "start_time": _server_start_time,
    }


@router.post("/restart")
async def restart_server():
    """
    Gracefully stop the engine, then spawn a fresh uvicorn process and exit.
    Uses subprocess.Popen + os._exit to avoid Python 3.14 os.execv import
    shadowing issues (uvicorn's logging.py shadows stdlib logging on re-exec).
    """
    logger.info("Server: restart requested via API")

    def _do_restart():
        time.sleep(0.5)  # let the HTTP response flush
        _graceful_engine_stop()
        _release_lock()
        logger.info("Server: spawning new process and exiting...")
        # Spawn a detached child process with the same arguments
        subprocess.Popen(
            [sys.executable] + sys.argv,
            cwd=os.getcwd(),
            start_new_session=True,
        )
        os._exit(0)

    threading.Thread(target=_do_restart, daemon=True).start()
    return {"status": "restarting", "message": "Server will restart momentarily"}


@router.post("/shutdown")
async def shutdown_server():
    """
    Gracefully stop the engine and terminate the backend process.
    """
    logger.info("Server: shutdown requested via API")

    def _do_shutdown():
        time.sleep(0.5)  # let the HTTP response flush
        _graceful_engine_stop()
        _release_lock()
        logger.info("Server: exiting process")
        os._exit(0)

    threading.Thread(target=_do_shutdown, daemon=True).start()
    return {"status": "shutting_down", "message": "Server will stop momentarily"}
