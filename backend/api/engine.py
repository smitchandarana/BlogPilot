import time
from fastapi import APIRouter, HTTPException
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
