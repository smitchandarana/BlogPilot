import time
import threading
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from backend.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

_start_time: float = 0


def _get_engine():
    try:
        from backend.core.engine import engine
        return engine
    except Exception:
        return None


@router.post("/start")
async def start_engine():
    eng = _get_engine()
    if eng:
        try:
            global _start_time
            _start_time = time.time()
            eng.start()
            return {"state": eng.status()["state"]}
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
    return {"state": "RUNNING"}


@router.post("/stop")
async def stop_engine():
    eng = _get_engine()
    if eng:
        try:
            eng.stop()
            return {"state": eng.status()["state"]}
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
    return {"state": "STOPPED"}


@router.post("/pause")
async def pause_engine():
    eng = _get_engine()
    if eng:
        try:
            eng.pause()
            return {"state": eng.status()["state"]}
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
    return {"state": "PAUSED"}


@router.post("/resume")
async def resume_engine():
    eng = _get_engine()
    if eng:
        try:
            eng.resume()
            return {"state": eng.status()["state"]}
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
    return {"state": "RUNNING"}


@router.post("/scan-now")
async def trigger_scan():
    """Manually trigger a feed scan immediately (bypasses scheduler interval)."""
    eng = _get_engine()
    if not eng:
        raise HTTPException(status_code=503, detail="Engine not initialised")
    from backend.core.state_manager import EngineState
    if eng.state_manager.get() != EngineState.RUNNING:
        raise HTTPException(status_code=409, detail="Engine must be RUNNING")
    eng.queue_feed_scan()
    return {"status": "feed_scan_queued"}


@router.post("/reset-circuit-breaker")
async def reset_circuit_breaker():
    """Manually reset the circuit breaker after investigating errors."""
    eng = _get_engine()
    if not eng:
        raise HTTPException(status_code=503, detail="Engine not initialised")
    if hasattr(eng, "circuit_breaker") and eng.circuit_breaker:
        eng.circuit_breaker.reset()
        # If engine is in ERROR state, recover to STOPPED
        from backend.core.state_manager import EngineState
        if eng.state_manager.get() == EngineState.ERROR:
            eng.state_manager.recover()
        return {"status": "circuit_breaker_reset", "state": eng.status()["state"]}
    return {"status": "no_circuit_breaker"}


@router.get("/status")
async def get_status():
    eng = _get_engine()
    if eng:
        return eng.status()
    uptime = int(time.time() - _start_time) if _start_time else 0
    return {
        "state": "STOPPED",
        "uptime_seconds": uptime,
        "tasks_queued": 0,
        "active_workers": 0,
    }


# ── Comment preview approval ───────────────────────────────────────────────

@router.get("/pending-previews")
async def get_pending_previews():
    """
    Return all posts currently in PREVIEW state (awaiting human approval).
    Called by the Dashboard PreviewQueue panel on mount.
    """
    from backend.storage.database import get_db
    from backend.storage.models import Post

    with get_db() as db:
        posts = (
            db.query(Post)
            .filter(Post.state == "PREVIEW")
            .order_by(Post.created_at.desc())
            .limit(50)
            .all()
        )
        return [
            {
                "post_id": p.id,
                "url": p.url,
                "author": p.author_name or "Unknown",
                "snippet": (p.text or "")[:200],
                "comment": p.comment_text or "",
                "score": round(p.relevance_score or 0.0, 1),
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in posts
        ]


class _ApproveRequest(BaseModel):
    post_id: str
    comment_text: str = Field(..., max_length=1250)


@router.post("/approve-comment")
async def approve_comment(req: _ApproveRequest):
    """
    Approve a preview comment and queue it for posting on LinkedIn.
    Requires engine to be RUNNING (browser session is opened by worker).
    """
    eng = _get_engine()
    if not eng:
        raise HTTPException(status_code=503, detail="Engine not initialised")
    from backend.core.state_manager import EngineState
    if eng.state_manager.get() != EngineState.RUNNING:
        raise HTTPException(
            status_code=409,
            detail="Engine must be RUNNING to post comments. Start the engine first.",
        )
    from backend.storage.database import get_db
    from backend.storage.models import Post as _Post
    with get_db() as _db:
        _post = _db.query(_Post).filter_by(id=req.post_id).first()
        if not _post:
            raise HTTPException(status_code=404, detail=f"Post '{req.post_id}' not found")
        if _post.state != "PREVIEW":
            raise HTTPException(
                status_code=409,
                detail=f"Post is in state '{_post.state}', not 'PREVIEW'. Cannot approve.",
            )
    from backend.core.pipeline import run_approve_comment
    future = eng.worker_pool.submit(run_approve_comment, req.post_id, req.comment_text)
    if future is None:
        raise HTTPException(status_code=503, detail="Worker pool is full or engine not RUNNING")
    return {"status": "approval_queued", "post_id": req.post_id}


@router.post("/run-comment-monitor")
async def run_comment_monitor():
    """
    Manually trigger the comment monitor — checks recent comments for replies
    to feed the self-learning loop. Runs in a background thread; returns immediately.
    """
    def _run():
        try:
            from backend.learning.comment_monitor import run_comment_monitor as _monitor
            _monitor()
        except Exception as exc:
            logger.warning(f"Manual comment_monitor error: {exc}")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return {"status": "comment_monitor_started"}


class _RejectRequest(BaseModel):
    post_id: str


@router.post("/reject-comment")
async def reject_comment(req: _RejectRequest):
    """
    Reject a preview comment — marks the post as SKIPPED (no browser needed).
    """
    from backend.storage.database import get_db
    from backend.storage.models import Post
    from backend.storage import post_state

    with get_db() as db:
        post = db.query(Post).filter_by(id=req.post_id).first()
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        post_state.update_state(post.url, "SKIPPED", db, skip_reason="rejected in preview")

    return {"status": "rejected", "post_id": req.post_id}
