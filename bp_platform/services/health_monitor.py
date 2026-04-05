"""Background health monitor — polls container /health endpoints.

Also monitors Tailscale exit node connectivity. If the exit node (home IP)
goes offline, ALL running LinkedIn engines are paused immediately to prevent
LinkedIn automation from leaking out through the Oracle Cloud datacenter IP.
Engines are automatically resumed when the exit node reconnects.
"""

import asyncio
import logging
import subprocess
from datetime import datetime

import httpx

from bp_platform.config import (
    HEALTH_CHECK_INTERVAL_SECONDS,
    HEALTH_CHECK_MAX_FAILURES,
    HEALTH_CHECK_MAX_RESTARTS,
    TAILSCALE_EXIT_NODE,
)
from bp_platform.models.database import Container, get_db
from bp_platform.services import container_manager

logger = logging.getLogger("platform.health_monitor")

# Tailscale exit node state — tracks whether we were previously connected
# so we only act on transitions (connected→dropped or dropped→reconnected).
_ts_was_connected: bool | None = None   # None = not yet checked
_ts_paused_user_ids: set[str] = set()  # user IDs we auto-paused due to TS drop


async def health_monitor_loop():
    """Run forever, polling container health and Tailscale status every N seconds."""
    logger.info("Health monitor started")
    while True:
        try:
            # Check Tailscale first — if it's down, pause engines before health checks
            if TAILSCALE_EXIT_NODE:
                await _check_tailscale_exit_node()
            await _check_all_containers()
        except Exception as e:
            logger.error(f"Health monitor error: {e}")
        await asyncio.sleep(HEALTH_CHECK_INTERVAL_SECONDS)


# ── Tailscale exit node monitor ───────────────────────────────────────────

async def _check_tailscale_exit_node():
    """
    Ping the Tailscale exit node. On disconnect: pause all running engines.
    On reconnect: resume the engines that were paused by this monitor.
    """
    global _ts_was_connected, _ts_paused_user_ids

    connected = await _ping_tailscale_exit_node()

    if _ts_was_connected is None:
        # First check — just record state, no action
        _ts_was_connected = connected
        logger.info(f"Tailscale exit node {TAILSCALE_EXIT_NODE}: {'connected' if connected else 'OFFLINE'}")
        return

    if _ts_was_connected and not connected:
        # Transition: connected → dropped
        logger.warning(
            f"Tailscale exit node {TAILSCALE_EXIT_NODE} went OFFLINE — "
            "pausing all running LinkedIn engines to protect IP"
        )
        _ts_paused_user_ids = await _pause_all_running_engines(reason="tailscale_disconnect")
        _ts_was_connected = False

    elif not _ts_was_connected and connected:
        # Transition: dropped → reconnected
        logger.info(
            f"Tailscale exit node {TAILSCALE_EXIT_NODE} reconnected — "
            f"resuming {len(_ts_paused_user_ids)} engine(s)"
        )
        await _resume_engines(_ts_paused_user_ids)
        _ts_paused_user_ids = set()
        _ts_was_connected = True


async def _ping_tailscale_exit_node() -> bool:
    """Ping the exit node IP via Tailscale network. Returns True if reachable."""
    try:
        # Use system ping — 1 packet, 3s timeout, works on Linux (Oracle VM)
        result = await asyncio.to_thread(
            subprocess.run,
            ["ping", "-c", "1", "-W", "3", TAILSCALE_EXIT_NODE],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception as e:
        logger.debug(f"Tailscale ping failed: {e}")
        return False


async def _pause_all_running_engines(reason: str) -> set[str]:
    """
    Tell every running engine to pause via its /engine/pause endpoint.
    Returns the set of user_ids that were successfully paused.
    """
    with get_db() as db:
        running = (
            db.query(Container)
            .filter(Container.status == "running", Container.engine_state == "RUNNING")
            .all()
        )
        targets = [
            {"user_id": c.user_id, "container_name": c.container_name, "api_token": c.api_token}
            for c in running
        ]

    paused: set[str] = set()
    async with httpx.AsyncClient(timeout=10) as client:
        for t in targets:
            try:
                resp = await client.post(
                    f"http://{t['container_name']}:8000/engine/pause",
                    headers={"Authorization": f"Bearer {t['api_token']}"},
                )
                if resp.status_code in (200, 409):  # 409 = already paused
                    paused.add(t["user_id"])
                    logger.info(f"Paused engine for user {t['user_id']} ({reason})")
            except Exception as e:
                logger.error(f"Failed to pause engine for user {t['user_id']}: {e}")

    return paused


async def _resume_engines(user_ids: set[str]):
    """Resume engines for the given user IDs after Tailscale reconnects."""
    if not user_ids:
        return

    with get_db() as db:
        containers = (
            db.query(Container)
            .filter(Container.user_id.in_(user_ids), Container.status == "running")
            .all()
        )
        targets = [
            {"user_id": c.user_id, "container_name": c.container_name, "api_token": c.api_token}
            for c in containers
        ]

    async with httpx.AsyncClient(timeout=10) as client:
        for t in targets:
            try:
                resp = await client.post(
                    f"http://{t['container_name']}:8000/engine/resume",
                    headers={"Authorization": f"Bearer {t['api_token']}"},
                )
                if resp.status_code == 200:
                    logger.info(f"Resumed engine for user {t['user_id']} (tailscale_reconnect)")
            except Exception as e:
                logger.error(f"Failed to resume engine for user {t['user_id']}: {e}")


# ── Container health checks ───────────────────────────────────────────────

async def _check_all_containers():
    """Poll all running containers."""
    with get_db() as db:
        containers = (
            db.query(Container)
            .filter(Container.status == "running")
            .all()
        )
        container_data = [
            {
                "id": c.id,
                "user_id": c.user_id,
                "container_name": c.container_name,
                "api_token": c.api_token,
                "health_check_failures": c.health_check_failures or 0,
                "restart_count": c.restart_count or 0,
            }
            for c in containers
        ]

    async with httpx.AsyncClient(timeout=10) as client:
        for c in container_data:
            await _check_one(client, c)


async def _check_one(client: httpx.AsyncClient, c: dict):
    """Check a single container's health via Docker network DNS."""
    name = c["container_name"]
    try:
        resp = await client.get(
            f"http://{name}:8000/health",
            headers={"Authorization": f"Bearer {c['api_token']}"},
        )
        if resp.status_code == 200:
            data = resp.json()
            _update_health(c["id"], healthy=True, engine_state=data.get("engine_state"))
            return
    except Exception:
        pass

    # Failed
    failures = c["health_check_failures"] + 1
    _update_health(c["id"], healthy=False, failures=failures)

    if failures >= HEALTH_CHECK_MAX_FAILURES:
        if c["restart_count"] < HEALTH_CHECK_MAX_RESTARTS:
            logger.warning(f"Container {c['id']} unhealthy ({failures} failures), restarting...")
            try:
                await asyncio.to_thread(container_manager.restart_container, c["user_id"])
                _update_health(c["id"], healthy=False, failures=0)
            except Exception as e:
                logger.error(f"Failed to restart container {c['id']}: {e}")
                _mark_error(c["id"])
        else:
            logger.error(f"Container {c['id']} exceeded max restarts, marking ERROR")
            _mark_error(c["id"])


def _update_health(container_id: str, healthy: bool, engine_state: str = None,
                   failures: int = None):
    with get_db() as db:
        c = db.query(Container).filter_by(id=container_id).first()
        if c:
            c.health_status = "healthy" if healthy else "unhealthy"
            c.last_health_check = datetime.utcnow()
            if engine_state is not None:
                c.engine_state = engine_state
            if failures is not None:
                c.health_check_failures = failures
            elif healthy:
                c.health_check_failures = 0
            db.commit()


def _mark_error(container_id: str):
    with get_db() as db:
        c = db.query(Container).filter_by(id=container_id).first()
        if c:
            c.status = "error"
            c.health_status = "unhealthy"
            db.commit()
