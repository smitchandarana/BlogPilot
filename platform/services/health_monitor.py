"""Background health monitor — polls container /health endpoints."""

import asyncio
import logging
from datetime import datetime

import httpx

from platform.config import (
    HEALTH_CHECK_INTERVAL_SECONDS,
    HEALTH_CHECK_MAX_FAILURES,
    HEALTH_CHECK_MAX_RESTARTS,
)
from platform.models.database import Container, get_db
from platform.services import container_manager

logger = logging.getLogger("platform.health_monitor")


async def health_monitor_loop():
    """Run forever, polling container health every N seconds."""
    logger.info("Health monitor started")
    while True:
        try:
            await _check_all_containers()
        except Exception as e:
            logger.error(f"Health monitor error: {e}")
        await asyncio.sleep(HEALTH_CHECK_INTERVAL_SECONDS)


async def _check_all_containers():
    """Poll all running containers."""
    with get_db() as db:
        containers = (
            db.query(Container)
            .filter(Container.status == "running")
            .all()
        )
        # Detach from session before async work
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
                container_manager.restart_container(c["user_id"])
                _update_health(c["id"], healthy=False, failures=0)  # Reset counter after restart
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
