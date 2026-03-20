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
        # Use scripts/start_server.py to avoid Python 3.14 + uvicorn logging.py
        # shadow issue: when spawned as child, site-packages/uvicorn/ lands in
        # sys.path and shadows stdlib logging, breaking the new process.
        # The helper script filters sys.path before importing uvicorn.
        start_script = os.path.join(os.getcwd(), "scripts", "start_server.py")
        subprocess.Popen(
            [sys.executable, start_script],
            cwd=os.getcwd(),
            start_new_session=True,
        )
        os._exit(0)

    threading.Thread(target=_do_restart, daemon=True).start()
    return {"status": "restarting", "message": "Server will restart momentarily"}


@router.post("/clear-data")
async def clear_all_data():
    """
    Delete all user-generated data: posts, leads, action logs, campaigns,
    campaign enrollments, scheduled posts, quality logs, topic performance,
    research snippets, researched topics, content insights, content patterns,
    generation sessions. Budget counters are reset to 0. Settings are preserved.
    """
    from backend.storage.database import get_db
    from backend.storage.models import (
        Post, Lead, ActionLog, Campaign, CampaignEnrollment,
        Budget, ScheduledPost, CommentQualityLog, PostQualityLog,
        TopicPerformance,
    )

    deleted: dict = {}
    with get_db() as db:
        for Model in [
            CampaignEnrollment, Campaign, ActionLog, Post, Lead,
            ScheduledPost, CommentQualityLog, PostQualityLog, TopicPerformance,
        ]:
            count = db.query(Model).delete(synchronize_session=False)
            deleted[Model.__tablename__] = count

        # Reset budget counters to 0 (keep rows — they store limits too)
        db.query(Budget).update({"count_today": 0}, synchronize_session=False)
        db.commit()

    # Also clear research + intelligence tables if models exist
    try:
        with get_db() as db:
            from backend.storage.models import ResearchSnippet, ResearchedTopic
            deleted["research_snippets"] = db.query(ResearchSnippet).delete(synchronize_session=False)
            deleted["researched_topics"] = db.query(ResearchedTopic).delete(synchronize_session=False)
            db.commit()
    except Exception:
        pass

    try:
        with get_db() as db:
            from backend.storage.models import ContentInsight, ContentPattern, GenerationSession
            deleted["content_insights"] = db.query(ContentInsight).delete(synchronize_session=False)
            deleted["content_patterns"] = db.query(ContentPattern).delete(synchronize_session=False)
            deleted["generation_sessions"] = db.query(GenerationSession).delete(synchronize_session=False)
            db.commit()
    except Exception:
        pass

    logger.warning(f"Server: clear-all-data executed — rows deleted: {deleted}")
    return {"cleared": True, "deleted": deleted}


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
