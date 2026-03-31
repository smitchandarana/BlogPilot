"""Admin endpoints — user management, system stats, container control."""

import psutil
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends

from bp_platform.api.auth import require_admin
from bp_platform.models.database import User, Container, AuditLog, get_db
from bp_platform.services import container_manager

router = APIRouter(prefix="/platform/admin", tags=["admin"])


@router.get("/users")
async def list_users(admin: dict = Depends(require_admin)):
    """List all users with container status."""
    with get_db() as db:
        users = db.query(User).order_by(User.created_at.desc()).all()
        result = []
        for u in users:
            c = db.query(Container).filter_by(user_id=u.id).first()
            result.append({
                "id": u.id,
                "email": u.email,
                "name": u.name,
                "role": u.role,
                "subscription_status": u.subscription_status,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat(),
                "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
                "container": {
                    "status": c.status if c else None,
                    "health_status": c.health_status if c else None,
                    "engine_state": c.engine_state if c else None,
                    "host_port": c.host_port if c else None,
                    "restart_count": c.restart_count if c else 0,
                } if c else None,
            })
        return result


@router.get("/users/{user_id}")
async def get_user(user_id: str, admin: dict = Depends(require_admin)):
    """Get detailed user info."""
    with get_db() as db:
        u = db.query(User).filter_by(id=user_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="User not found")
        c = db.query(Container).filter_by(user_id=user_id).first()
        return {
            "user": {
                "id": u.id, "email": u.email, "name": u.name,
                "role": u.role, "subscription_status": u.subscription_status,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat(),
                "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            },
            "container": container_manager.get_container_status(user_id) if c else None,
        }


@router.post("/users/{user_id}/suspend")
async def suspend_user(user_id: str, admin: dict = Depends(require_admin)):
    """Suspend user and stop their container."""
    with get_db() as db:
        u = db.query(User).filter_by(id=user_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="User not found")
        u.is_active = False
        u.subscription_status = "suspended"
        db.commit()

    try:
        container_manager.stop_container(user_id)
    except Exception:
        pass  # container might not exist

    _audit(admin["sub"], "admin.suspend_user", {"target_user_id": user_id})
    return {"status": "suspended"}


@router.post("/users/{user_id}/unsuspend")
async def unsuspend_user(user_id: str, admin: dict = Depends(require_admin)):
    """Reactivate a suspended user."""
    with get_db() as db:
        u = db.query(User).filter_by(id=user_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="User not found")
        u.is_active = True
        u.subscription_status = "active"
        db.commit()

    _audit(admin["sub"], "admin.unsuspend_user", {"target_user_id": user_id})
    return {"status": "active"}


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin: dict = Depends(require_admin)):
    """Delete user and destroy their container + data."""
    try:
        container_manager.destroy_container(user_id, delete_volumes=True)
    except Exception:
        pass

    with get_db() as db:
        u = db.query(User).filter_by(id=user_id).first()
        if u:
            db.delete(u)
            db.commit()

    _audit(admin["sub"], "admin.delete_user", {"target_user_id": user_id})
    return {"status": "deleted"}


@router.get("/containers")
async def list_containers(admin: dict = Depends(require_admin)):
    """List all containers with health and resource info."""
    with get_db() as db:
        containers = db.query(Container).filter(Container.status != "destroyed").all()
        result = []
        for c in containers:
            user = db.query(User).filter_by(id=c.user_id).first()
            entry = {
                "id": c.id,
                "user_email": user.email if user else "unknown",
                "container_name": c.container_name,
                "host_port": c.host_port,
                "status": c.status,
                "health_status": c.health_status,
                "engine_state": c.engine_state,
                "started_at": c.started_at.isoformat() if c.started_at else None,
                "restart_count": c.restart_count,
            }
            result.append(entry)
        return result


@router.post("/containers/{container_id}/restart")
async def admin_restart(container_id: str, admin: dict = Depends(require_admin)):
    """Force restart any container by ID."""
    with get_db() as db:
        c = db.query(Container).filter_by(id=container_id).first()
        if not c:
            raise HTTPException(status_code=404, detail="Container not found")
        user_id = c.user_id

    container_manager.restart_container(user_id)
    _audit(admin["sub"], "admin.restart_container", {"container_id": container_id})
    return {"status": "restarted"}


@router.get("/system")
async def system_stats(admin: dict = Depends(require_admin)):
    """System resource stats."""
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    with get_db() as db:
        total_users = db.query(User).count()
        active_containers = db.query(Container).filter(Container.status == "running").count()
        total_containers = db.query(Container).filter(Container.status != "destroyed").count()

    return {
        "memory": {
            "total_gb": round(mem.total / (1024**3), 1),
            "used_gb": round(mem.used / (1024**3), 1),
            "available_gb": round(mem.available / (1024**3), 1),
            "percent": mem.percent,
        },
        "disk": {
            "total_gb": round(disk.total / (1024**3), 1),
            "used_gb": round(disk.used / (1024**3), 1),
            "free_gb": round(disk.free / (1024**3), 1),
            "percent": disk.percent,
        },
        "cpu_percent": psutil.cpu_percent(interval=1),
        "users": total_users,
        "containers_running": active_containers,
        "containers_total": total_containers,
        "max_containers": 6,  # Based on 16 GB RAM / 2 GB per container
    }


def _audit(admin_id: str, action: str, details: dict = None):
    """Write an audit log entry."""
    try:
        with get_db() as db:
            db.add(AuditLog(user_id=admin_id, action=action, details=details))
            db.commit()
    except Exception:
        pass
