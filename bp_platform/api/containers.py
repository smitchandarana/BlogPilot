"""Container lifecycle endpoints — provision, start, stop, restart, destroy, reset."""

from fastapi import APIRouter, HTTPException, Depends

from bp_platform.api.auth import get_current_user
from bp_platform.models.database import User, Container, get_db
from bp_platform.services import container_manager

router = APIRouter(prefix="/platform/containers", tags=["containers"])


@router.post("/provision")
async def provision(user: dict = Depends(get_current_user)):
    """Create and start a new BlogPilot container for the current user."""
    user_id = user["sub"]

    # Check subscription
    with get_db() as db:
        u = db.query(User).filter_by(id=user_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="User not found")
        if u.subscription_status not in ("active", "pending") and u.role != "admin":
            raise HTTPException(status_code=402, detail="Active subscription required")

        # Check if container already exists
        existing = db.query(Container).filter_by(user_id=user_id).first()
        if existing and existing.status != "destroyed":
            raise HTTPException(status_code=409, detail="Container already exists")

    try:
        is_admin = user.get("role") == "admin"
        record = container_manager.provision_container(user_id, is_admin=is_admin)
        return {
            "status": "running",
            "container_name": record.container_name,
            "api_token": record.api_token,
        }
    except RuntimeError:
        raise HTTPException(status_code=503, detail="No available capacity. Try again later.")


@router.post("/start")
async def start(user: dict = Depends(get_current_user)):
    """Start a stopped container."""
    try:
        container_manager.start_container(user["sub"])
        return {"status": "running"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Container start failed")


@router.post("/stop")
async def stop(user: dict = Depends(get_current_user)):
    """Stop a running container."""
    try:
        container_manager.stop_container(user["sub"])
        return {"status": "stopped"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/restart")
async def restart(user: dict = Depends(get_current_user)):
    """Restart the container."""
    try:
        container_manager.restart_container(user["sub"])
        return {"status": "running"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("")
async def destroy(user: dict = Depends(get_current_user), delete_data: bool = False):
    """Destroy the container. Optionally delete all user data."""
    try:
        container_manager.destroy_container(user["sub"], delete_volumes=delete_data)
        return {"status": "destroyed"}
    except Exception:
        raise HTTPException(status_code=500, detail="Container destroy failed")


@router.post("/reset")
async def reset(user: dict = Depends(get_current_user)):
    """Reset container to default settings. Keeps browser profile (LinkedIn session)."""
    try:
        container_manager.reset_container(user["sub"])
        return {"status": "reset_complete"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/status")
async def status(user: dict = Depends(get_current_user)):
    """Get container status."""
    return container_manager.get_container_status(user["sub"])
