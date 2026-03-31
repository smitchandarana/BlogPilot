"""Docker container lifecycle management for BlogPilot user instances."""

import os
import shutil
import time
import secrets
from datetime import datetime

import docker
import httpx

from platform.config import (
    BLOGPILOT_IMAGE, VOLUME_BASE_PATH, DOCKER_NETWORK,
    CONTAINER_MEMORY_LIMIT, CONTAINER_CPU_LIMIT,
    ADMIN_SETTINGS_TEMPLATE, DEFAULT_SETTINGS_TEMPLATE,
)
from platform.services.port_allocator import allocate_port
from platform.services.token_service import generate_container_token
from platform.models.database import Container, get_db

_client = None


def _docker() -> docker.DockerClient:
    global _client
    if _client is None:
        _client = docker.from_env()
    return _client


def provision_container(user_id: str, is_admin: bool = False) -> Container:
    """Create volume dirs, seed config, start Docker container, return Container record."""
    port = allocate_port()
    token = generate_container_token()
    name = f"blogpilot-{user_id[:8]}"

    # Create volume directories
    vol_root = os.path.join(VOLUME_BASE_PATH, user_id)
    for subdir in ("data", "browser_profile", "config", "config/.secrets", "logs"):
        os.makedirs(os.path.join(vol_root, subdir), exist_ok=True)

    # Seed settings.yaml from template
    template = ADMIN_SETTINGS_TEMPLATE if is_admin else DEFAULT_SETTINGS_TEMPLATE
    settings_dest = os.path.join(vol_root, "config", "settings.yaml")
    if os.path.isfile(template):
        shutil.copy2(template, settings_dest)

    # Copy prompts into user volume
    prompts_src = os.path.join(os.path.dirname(__file__), "..", "..", "prompts")
    prompts_dest = os.path.join(vol_root, "prompts")
    if os.path.isdir(prompts_src) and not os.path.isdir(prompts_dest):
        shutil.copytree(prompts_src, prompts_dest)

    # Write API token
    token_path = os.path.join(vol_root, "config", ".secrets", ".api_token")
    with open(token_path, "w") as f:
        f.write(token)

    # Traefik labels for dynamic routing
    labels = {
        "traefik.enable": "true",
        f"traefik.http.routers.{name}.rule": f"Host(`api.phoenixsolution.in`) && PathPrefix(`/u/{user_id}`)",
        f"traefik.http.routers.{name}.entrypoints": "websecure",
        f"traefik.http.routers.{name}.tls.certresolver": "letsencrypt",
        f"traefik.http.middlewares.{name}-strip.stripprefix.prefixes": f"/u/{user_id}",
        f"traefik.http.routers.{name}.middlewares": f"{name}-strip",
        f"traefik.http.services.{name}.loadbalancer.server.port": "8000",
        "traefik.docker.network": DOCKER_NETWORK,
    }

    # Volume mounts (host path : container path)
    vol_root_abs = os.path.abspath(vol_root)
    volumes = {
        os.path.join(vol_root_abs, "data"): {"bind": "/app/data", "mode": "rw"},
        os.path.join(vol_root_abs, "browser_profile"): {"bind": "/app/browser_profile", "mode": "rw"},
        os.path.join(vol_root_abs, "config"): {"bind": "/app/config", "mode": "rw"},
        os.path.join(vol_root_abs, "logs"): {"bind": "/app/logs", "mode": "rw"},
        os.path.join(vol_root_abs, "prompts"): {"bind": "/app/prompts", "mode": "rw"},
    }

    # Start container — no host port mapping; traffic routed only via Traefik on Docker network
    container = _docker().containers.run(
        image=BLOGPILOT_IMAGE,
        name=name,
        detach=True,
        volumes=volumes,
        labels=labels,
        network=DOCKER_NETWORK,
        mem_limit=CONTAINER_MEMORY_LIMIT,
        nano_cpus=int(CONTAINER_CPU_LIMIT * 1e9),
        environment={
            "BLOGPILOT_CONTAINER": "1",
            "BLOGPILOT_BASE_DIR": "/app",
            "BLOGPILOT_DATA_DIR": "/app/data",
            "BLOGPILOT_CONFIG": "/app/config/settings.yaml",
            "BIND_HOST": "0.0.0.0",
            "BIND_PORT": "8000",
        },
        restart_policy={"Name": "unless-stopped"},
    )

    # Save to platform DB
    with get_db() as db:
        record = Container(
            user_id=user_id,
            docker_container_id=container.id,
            container_name=name,
            host_port=port,
            status="starting",
            api_token=token,
            volume_path=vol_root_abs,
        )
        db.add(record)
        db.commit()
        db.refresh(record)

    # Wait for health check via Docker network DNS
    _wait_healthy(name, timeout=60)

    with get_db() as db:
        rec = db.query(Container).filter_by(user_id=user_id).first()
        if rec:
            rec.status = "running"
            rec.started_at = datetime.utcnow()
            rec.health_status = "healthy"
            db.commit()

    return record


def start_container(user_id: str) -> None:
    """Start a stopped container."""
    with get_db() as db:
        rec = db.query(Container).filter_by(user_id=user_id).first()
        if not rec or not rec.docker_container_id:
            raise ValueError("No container found for user")
        rec.status = "starting"
        db.commit()

    try:
        c = _docker().containers.get(rec.docker_container_id)
        c.start()
        _wait_healthy(rec.container_name, timeout=60)

        with get_db() as db:
            rec = db.query(Container).filter_by(user_id=user_id).first()
            rec.status = "running"
            rec.started_at = datetime.utcnow()
            rec.health_status = "healthy"
            db.commit()
    except Exception as e:
        with get_db() as db:
            rec = db.query(Container).filter_by(user_id=user_id).first()
            rec.status = "error"
            db.commit()
        raise


def stop_container(user_id: str) -> None:
    """Stop a running container."""
    with get_db() as db:
        rec = db.query(Container).filter_by(user_id=user_id).first()
        if not rec or not rec.docker_container_id:
            raise ValueError("No container found for user")
        rec.status = "stopping"
        db.commit()

    c = _docker().containers.get(rec.docker_container_id)
    c.stop(timeout=30)

    with get_db() as db:
        rec = db.query(Container).filter_by(user_id=user_id).first()
        rec.status = "stopped"
        rec.stopped_at = datetime.utcnow()
        rec.health_status = "unknown"
        db.commit()


def restart_container(user_id: str) -> None:
    """Restart a container."""
    with get_db() as db:
        rec = db.query(Container).filter_by(user_id=user_id).first()
        if not rec or not rec.docker_container_id:
            raise ValueError("No container found for user")

    c = _docker().containers.get(rec.docker_container_id)
    c.restart(timeout=30)

    with get_db() as db:
        rec = db.query(Container).filter_by(user_id=user_id).first()
        rec.status = "running"
        rec.restart_count = (rec.restart_count or 0) + 1
        rec.started_at = datetime.utcnow()
        db.commit()


def destroy_container(user_id: str, delete_volumes: bool = False) -> None:
    """Remove container. Optionally delete user volumes."""
    with get_db() as db:
        rec = db.query(Container).filter_by(user_id=user_id).first()
        if not rec:
            return

    try:
        c = _docker().containers.get(rec.docker_container_id)
        c.stop(timeout=10)
        c.remove(force=True)
    except docker.errors.NotFound:
        pass

    if delete_volumes and rec.volume_path and os.path.isdir(rec.volume_path):
        shutil.rmtree(rec.volume_path, ignore_errors=True)

    with get_db() as db:
        rec = db.query(Container).filter_by(user_id=user_id).first()
        rec.status = "destroyed"
        rec.docker_container_id = None
        db.commit()


def reset_container(user_id: str) -> None:
    """Reset a user's container to default settings (keeps browser profile)."""
    with get_db() as db:
        rec = db.query(Container).filter_by(user_id=user_id).first()
        if not rec or not rec.volume_path:
            raise ValueError("No container found for user")

    # Replace settings.yaml with default template
    settings_dest = os.path.join(rec.volume_path, "config", "settings.yaml")
    if os.path.isfile(DEFAULT_SETTINGS_TEMPLATE):
        shutil.copy2(DEFAULT_SETTINGS_TEMPLATE, settings_dest)

    # Reset prompts to defaults
    prompts_src = os.path.join(os.path.dirname(__file__), "..", "..", "prompts")
    prompts_dest = os.path.join(rec.volume_path, "prompts")
    if os.path.isdir(prompts_src):
        shutil.rmtree(prompts_dest, ignore_errors=True)
        shutil.copytree(prompts_src, prompts_dest)

    # Restart container to pick up changes
    restart_container(user_id)


def get_container_status(user_id: str) -> dict:
    """Get container status from DB + live Docker state."""
    with get_db() as db:
        rec = db.query(Container).filter_by(user_id=user_id).first()
        if not rec:
            return {"status": "none"}

    result = {
        "status": rec.status,
        "health_status": rec.health_status,
        "engine_state": rec.engine_state,
        "host_port": rec.host_port,
        "started_at": rec.started_at.isoformat() if rec.started_at else None,
        "restart_count": rec.restart_count,
    }

    # Get live Docker status
    try:
        c = _docker().containers.get(rec.docker_container_id)
        result["docker_status"] = c.status
    except Exception:
        result["docker_status"] = "not_found"

    return result


def _wait_healthy(container_name: str, timeout: int = 60) -> bool:
    """Poll container via Docker network DNS until it responds OK."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = httpx.get(f"http://{container_name}:8000/health", timeout=5)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False
