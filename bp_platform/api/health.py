"""Platform health endpoints."""

import asyncio
import subprocess
from fastapi import APIRouter, Depends
from sqlalchemy import text

from bp_platform.config import TAILSCALE_EXIT_NODE
from bp_platform.models.database import User, Container, get_db
from bp_platform.api.auth import require_admin
from bp_platform.services.health_monitor import _ts_was_connected, _ts_paused_user_ids

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Platform health check."""
    try:
        with get_db() as db:
            db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "service": "blogpilot-platform",
    }


@router.get("/platform/health/containers")
async def container_health_summary():
    """Aggregated health of all containers."""
    with get_db() as db:
        containers = db.query(Container).filter(Container.status != "destroyed").all()
        summary = {
            "total": len(containers),
            "running": sum(1 for c in containers if c.status == "running"),
            "stopped": sum(1 for c in containers if c.status == "stopped"),
            "error": sum(1 for c in containers if c.status == "error"),
            "healthy": sum(1 for c in containers if c.health_status == "healthy"),
            "unhealthy": sum(1 for c in containers if c.health_status == "unhealthy"),
        }
        return summary


@router.get("/platform/health/tailscale")
async def tailscale_status(admin: dict = Depends(require_admin)):
    """
    Live Tailscale exit node status.
    Returns current connectivity, exit node IP, and list of engines paused due to disconnect.
    SSH connection is NOT affected by exit node state — this only controls LinkedIn engine traffic.
    """
    if not TAILSCALE_EXIT_NODE:
        return {
            "enabled": False,
            "exit_node": None,
            "connected": None,
            "engines_paused_by_ts": [],
            "note": "TAILSCALE_EXIT_NODE not configured — containers use Oracle Cloud IP",
        }

    # Live ping check
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            ["ping", "-c", "1", "-W", "3", TAILSCALE_EXIT_NODE],
            capture_output=True,
            timeout=5,
        )
        connected = result.returncode == 0
    except Exception:
        connected = False

    return {
        "enabled": True,
        "exit_node": TAILSCALE_EXIT_NODE,
        "connected": connected,
        "last_known_state": _ts_was_connected,
        "engines_paused_by_ts": list(_ts_paused_user_ids),
        "note": (
            "All LinkedIn engines paused — exit node offline, protecting your IP"
            if not connected else
            "Exit node online — LinkedIn traffic exits through your home IP"
        ),
    }
