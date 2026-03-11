import asyncio
import json
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

# ── Async/sync bridge ──────────────────────────────────────────────────────
# The event loop is stored here at app startup so that synchronous code
# (state_manager callbacks, circuit_breaker trips running in threads) can
# schedule broadcasts without needing to be inside a coroutine.

_event_loop: Optional[asyncio.AbstractEventLoop] = None


def set_event_loop(loop: asyncio.AbstractEventLoop):
    """Register the running event loop. Call once during app lifespan startup."""
    global _event_loop
    _event_loop = loop


def schedule_broadcast(event: str, payload: dict):
    """
    Thread-safe, sync-safe broadcast.
    Schedules manager.broadcast() on the stored event loop.
    Safe to call from sync callbacks or background threads.
    """
    if _event_loop is not None and not _event_loop.is_closed():
        asyncio.run_coroutine_threadsafe(
            manager.broadcast(event, payload),
            _event_loop,
        )
    # If loop is not ready, the broadcast is silently dropped (engine not yet live)


class ConnectionManager:
    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.append(ws)
        logger.info(f"WebSocket client connected. Total: {len(self._connections)}")

    def disconnect(self, ws: WebSocket):
        if ws in self._connections:
            self._connections.remove(ws)
        logger.info(f"WebSocket client disconnected. Total: {len(self._connections)}")

    async def broadcast(self, event: str, payload: dict):
        message = json.dumps({"event": event, "data": payload})
        dead = []
        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            # Keep connection alive — client messages ignored for now
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)


# ── Broadcast helpers (called from deep modules) ───────────────────

async def broadcast_activity(
    action: str,
    target: str,
    result: str,
    comment: Optional[str] = None,
):
    await manager.broadcast("activity", {
        "action": action,
        "target": target,
        "result": result,
        "comment": comment,
    })


async def broadcast_state_change(state: str):
    await manager.broadcast("engine_state", {"state": state})


async def broadcast_budget_update(action_type: str, count: int, limit: int):
    await manager.broadcast("budget_update", {
        "action_type": action_type,
        "count": count,
        "limit": limit,
    })


async def broadcast_alert(level: str, message: str):
    await manager.broadcast("alert", {"level": level, "message": message})


async def broadcast_lead_added(name: str, company: str, email: Optional[str] = None):
    await manager.broadcast("lead_added", {
        "name": name,
        "company": company,
        "email": email,
    })


async def broadcast_stats_update(stats: dict):
    await manager.broadcast("stats_update", stats)
