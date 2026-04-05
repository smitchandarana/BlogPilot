"""Admin endpoints — user management, system stats, container control."""

import asyncio
import psutil
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, EmailStr

from bp_platform.api.auth import require_admin
from bp_platform.models.database import User, Container, AuditLog, get_db
from bp_platform.services import container_manager
from bp_platform.services.token_service import hash_password

router = APIRouter(prefix="/platform/admin", tags=["admin"])


# ── Schemas ───────────────────────────────────────────────────────────────

class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    name: str = ""
    role: str = "user"
    subscription_status: str = "active"
    provision_container: bool = False


class ChangeRoleRequest(BaseModel):
    role: str


# ── Helpers ───────────────────────────────────────────────────────────────

def _audit(admin_id: str, action: str, details: dict = None, ip_address: str = None):
    """Write an audit log entry."""
    try:
        with get_db() as db:
            db.add(AuditLog(
                user_id=admin_id,
                action=action,
                details=details,
                ip_address=ip_address,
            ))
            db.commit()
    except Exception:
        pass


def _user_row(u: User, c: Container | None) -> dict:
    """Serialize a user + optional container into the standard list shape."""
    return {
        "id": u.id,
        "email": u.email,
        "name": u.name,
        "role": u.role,
        "subscription_status": u.subscription_status,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat(),
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        "container": {
            "id": c.id,
            "status": c.status,
            "health_status": c.health_status,
            "engine_state": c.engine_state,
            "host_port": c.host_port,
            "restart_count": c.restart_count,
            "linkedin_email": c.linkedin_email,         # visible to admin
            "has_linkedin_password": bool(c.linkedin_password),  # never return password itself
        } if c else None,
    }


# ── Existing endpoints ────────────────────────────────────────────────────

@router.get("/users")
async def list_users(admin: dict = Depends(require_admin)):
    """List all users with container status."""
    with get_db() as db:
        users = db.query(User).order_by(User.created_at.desc()).all()
        result = []
        for u in users:
            c = db.query(Container).filter_by(user_id=u.id).first()
            result.append(_user_row(u, c))
        return result


@router.get("/users/{user_id}")
async def get_user(user_id: str, admin: dict = Depends(require_admin)):
    """Get detailed user info."""
    with get_db() as db:
        u = db.query(User).filter_by(id=user_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="User not found")
        c = db.query(Container).filter_by(user_id=user_id).first()
        has_container = c is not None

    container_status = None
    if has_container:
        try:
            container_status = await asyncio.to_thread(container_manager.get_container_status, user_id)
        except Exception:
            container_status = {"error": "Failed to retrieve container status"}
    return {
        "user": {
            "id": u.id, "email": u.email, "name": u.name,
            "role": u.role, "subscription_status": u.subscription_status,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat(),
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        },
        "container": container_status,
    }


@router.post("/users/{user_id}/suspend")
async def suspend_user(user_id: str, request: Request, admin: dict = Depends(require_admin)):
    """Suspend user and stop their container."""
    with get_db() as db:
        u = db.query(User).filter_by(id=user_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="User not found")
        u.is_active = False
        u.subscription_status = "suspended"
        db.commit()

    try:
        await asyncio.to_thread(container_manager.stop_container, user_id)
    except Exception:
        pass  # container might not exist

    _audit(admin["sub"], "admin.suspend_user", {"target_user_id": user_id}, _ip(request))
    return {"status": "suspended"}


@router.post("/users/{user_id}/unsuspend")
async def unsuspend_user(user_id: str, request: Request, admin: dict = Depends(require_admin)):
    """Reactivate a suspended user."""
    with get_db() as db:
        u = db.query(User).filter_by(id=user_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="User not found")
        u.is_active = True
        u.subscription_status = "active"
        db.commit()

    _audit(admin["sub"], "admin.unsuspend_user", {"target_user_id": user_id}, _ip(request))
    return {"status": "active"}


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, request: Request, admin: dict = Depends(require_admin)):
    """Delete user and destroy their container + data."""
    try:
        await asyncio.to_thread(container_manager.destroy_container, user_id, delete_volumes=True)
    except Exception:
        pass

    with get_db() as db:
        u = db.query(User).filter_by(id=user_id).first()
        if u:
            db.delete(u)
            db.commit()

    _audit(admin["sub"], "admin.delete_user", {"target_user_id": user_id}, _ip(request))
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
async def admin_restart(container_id: str, request: Request, admin: dict = Depends(require_admin)):
    """Force restart any container by ID."""
    with get_db() as db:
        c = db.query(Container).filter_by(id=container_id).first()
        if not c:
            raise HTTPException(status_code=404, detail="Container not found")
        user_id = c.user_id

    try:
        await asyncio.to_thread(container_manager.restart_container, user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Container restart failed")
    _audit(admin["sub"], "admin.restart_container", {"container_id": container_id}, _ip(request))
    return {"status": "restarted"}


@router.get("/system")
async def system_stats(admin: dict = Depends(require_admin)):
    """System resource stats."""
    import sys as _sys
    _disk_path = "C:\\" if _sys.platform == "win32" else "/"

    mem, disk, cpu = await asyncio.gather(
        asyncio.to_thread(psutil.virtual_memory),
        asyncio.to_thread(psutil.disk_usage, _disk_path),
        asyncio.to_thread(psutil.cpu_percent, interval=1),
    )

    with get_db() as db:
        total_users = db.query(User).count()
        active_containers = db.query(Container).filter(Container.status == "running").count()
        total_containers = db.query(Container).filter(Container.status != "destroyed").count()
        pending_users = db.query(User).filter_by(subscription_status="pending", is_active=False).count()

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
        "cpu_percent": cpu,
        "users": total_users,
        "containers_running": active_containers,
        "containers_total": total_containers,
        "max_containers": 6,  # Based on 16 GB RAM / 2 GB per container
        "pending_users": pending_users,
    }


# ── New endpoints ─────────────────────────────────────────────────────────

@router.post("/users")
async def create_user(req: CreateUserRequest, request: Request, admin: dict = Depends(require_admin)):
    """Admin creates a user account directly, optionally provisioning a container."""
    if len(req.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")
    if req.role not in ("user", "superuser", "admin"):
        raise HTTPException(status_code=422, detail="Role must be 'user', 'superuser', or 'admin'")
    valid_statuses = ("pending", "active", "suspended", "cancelled", "past_due")
    if req.subscription_status not in valid_statuses:
        raise HTTPException(status_code=422, detail=f"subscription_status must be one of: {', '.join(valid_statuses)}")

    with get_db() as db:
        existing = db.query(User).filter_by(email=req.email).first()
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")

        is_active = req.subscription_status == "active"
        user = User(
            email=req.email,
            password_hash=hash_password(req.password),
            name=req.name,
            role=req.role,
            subscription_status=req.subscription_status,
            is_active=is_active,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id
        user_email = user.email

    _audit(
        admin["sub"],
        "admin.create_user",
        {"target_user_id": user_id, "email": user_email, "role": req.role, "status": req.subscription_status},
        _ip(request),
    )

    # Optionally provision a container for the new user
    container_result = None
    if req.provision_container and is_active:
        try:
            c = await asyncio.to_thread(
                container_manager.provision_container, user_id, is_admin=(req.role == "admin")
            )
            container_result = {"status": c.status, "host_port": c.host_port}
            _audit(
                admin["sub"],
                "admin.provision_container",
                {"target_user_id": user_id, "triggered_by": "create_user"},
                _ip(request),
            )
        except Exception as e:
            container_result = {"error": str(e)}

    with get_db() as db:
        u = db.query(User).filter_by(id=user_id).first()
        c = db.query(Container).filter_by(user_id=user_id).first()
        return {**_user_row(u, c), "container_provisioned": container_result}


@router.post("/users/{user_id}/approve")
async def approve_user(user_id: str, request: Request, admin: dict = Depends(require_admin)):
    """Approve a pending signup — sets subscription to active and enables account."""
    with get_db() as db:
        u = db.query(User).filter_by(id=user_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="User not found")
        if u.subscription_status != "pending":
            raise HTTPException(status_code=409, detail=f"User is not pending (current status: {u.subscription_status})")
        u.subscription_status = "active"
        u.is_active = True
        db.commit()

    _audit(
        admin["sub"],
        "admin.approve_user",
        {"target_user_id": user_id},
        _ip(request),
    )
    return {"status": "active", "message": "User approved and account activated"}


@router.post("/users/{user_id}/reject")
async def reject_user(user_id: str, request: Request, admin: dict = Depends(require_admin)):
    """Reject a pending signup — marks account cancelled and inactive."""
    with get_db() as db:
        u = db.query(User).filter_by(id=user_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="User not found")
        if u.subscription_status != "pending":
            raise HTTPException(status_code=409, detail=f"User is not pending (current status: {u.subscription_status})")
        u.subscription_status = "cancelled"
        u.is_active = False
        db.commit()

    _audit(
        admin["sub"],
        "admin.reject_user",
        {"target_user_id": user_id},
        _ip(request),
    )
    return {"status": "cancelled", "message": "Signup rejected"}


@router.post("/users/{user_id}/pause")
async def pause_user(user_id: str, request: Request, admin: dict = Depends(require_admin)):
    """Pause a user — stops their container but keeps the account active."""
    with get_db() as db:
        u = db.query(User).filter_by(id=user_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="User not found")
        if not u.is_active:
            raise HTTPException(status_code=409, detail="User account is not active")
        c = db.query(Container).filter_by(user_id=user_id).first()

    if not c:
        raise HTTPException(status_code=404, detail="User has no container to pause")

    try:
        await asyncio.to_thread(container_manager.stop_container, user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop container: {e}")

    _audit(
        admin["sub"],
        "admin.pause_user",
        {"target_user_id": user_id},
        _ip(request),
    )
    return {"status": "paused", "message": "Container stopped; account remains active"}


@router.post("/users/{user_id}/resume")
async def resume_user(user_id: str, request: Request, admin: dict = Depends(require_admin)):
    """Resume a paused user — starts their container again."""
    with get_db() as db:
        u = db.query(User).filter_by(id=user_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="User not found")
        if not u.is_active:
            raise HTTPException(status_code=409, detail="User account is suspended — unsuspend first")
        c = db.query(Container).filter_by(user_id=user_id).first()

    if not c:
        raise HTTPException(status_code=404, detail="User has no container to resume")

    try:
        await asyncio.to_thread(container_manager.start_container, user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start container: {e}")

    _audit(
        admin["sub"],
        "admin.resume_user",
        {"target_user_id": user_id},
        _ip(request),
    )
    return {"status": "resumed", "message": "Container started"}


@router.post("/users/{user_id}/provision")
async def provision_user(user_id: str, request: Request, admin: dict = Depends(require_admin)):
    """Provision a container for a user who doesn't have one yet."""
    with get_db() as db:
        u = db.query(User).filter_by(id=user_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="User not found")
        existing = db.query(Container).filter_by(user_id=user_id).first()
        if existing:
            raise HTTPException(status_code=409, detail="User already has a container")
        is_admin = u.role == "admin"

    try:
        c = await asyncio.to_thread(container_manager.provision_container, user_id, is_admin=is_admin)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Provisioning failed: {e}")

    _audit(
        admin["sub"],
        "admin.provision_container",
        {"target_user_id": user_id},
        _ip(request),
    )
    return {
        "status": "provisioned",
        "container": {
            "id": c.id,
            "status": c.status,
            "host_port": c.host_port,
            "container_name": c.container_name,
        },
    }


@router.post("/users/{user_id}/change-role")
async def change_role(
    user_id: str,
    req: ChangeRoleRequest,
    request: Request,
    admin: dict = Depends(require_admin),
):
    """Change a user's role. Admins cannot change their own role."""
    if req.role not in ("user", "superuser", "admin"):
        raise HTTPException(status_code=422, detail="Role must be 'user', 'superuser', or 'admin'")
    if admin["sub"] == user_id:
        raise HTTPException(status_code=403, detail="You cannot change your own role")

    with get_db() as db:
        u = db.query(User).filter_by(id=user_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="User not found")
        old_role = u.role
        u.role = req.role
        db.commit()

    _audit(
        admin["sub"],
        "admin.change_role",
        {"target_user_id": user_id, "old_role": old_role, "new_role": req.role},
        _ip(request),
    )
    return {"status": "updated", "role": req.role}


class LinkedInCredentialsRequest(BaseModel):
    linkedin_email: str
    linkedin_password: str | None = None  # optional when updating existing credentials


@router.post("/users/{user_id}/linkedin-credentials")
async def set_linkedin_credentials(
    user_id: str,
    req: LinkedInCredentialsRequest,
    request: Request,
    admin: dict = Depends(require_admin),
):
    """Set LinkedIn credentials for a user's container. Password is stored as plaintext and never returned via API."""
    if not req.linkedin_email:
        raise HTTPException(status_code=422, detail="linkedin_email is required")

    with get_db() as db:
        c = db.query(Container).filter_by(user_id=user_id).first()
        if not c:
            raise HTTPException(status_code=404, detail="User has no container")
        # Require password if no existing credentials are set
        if not c.linkedin_password and not req.linkedin_password:
            raise HTTPException(status_code=422, detail="Password is required for new credentials")
        c.linkedin_email = req.linkedin_email.strip()
        if req.linkedin_password:
            c.linkedin_password = req.linkedin_password
        db.commit()

    _audit(
        admin["sub"],
        "admin.set_linkedin_credentials",
        {"target_user_id": user_id, "linkedin_email": req.linkedin_email},
        _ip(request),
    )
    return {"status": "saved", "linkedin_email": req.linkedin_email}


@router.delete("/users/{user_id}/linkedin-credentials")
async def clear_linkedin_credentials(
    user_id: str,
    request: Request,
    admin: dict = Depends(require_admin),
):
    """Clear stored LinkedIn credentials for a user's container."""
    with get_db() as db:
        c = db.query(Container).filter_by(user_id=user_id).first()
        if not c:
            raise HTTPException(status_code=404, detail="User has no container")
        c.linkedin_email = None
        c.linkedin_password = None
        db.commit()

    _audit(admin["sub"], "admin.clear_linkedin_credentials", {"target_user_id": user_id}, _ip(request))
    return {"status": "cleared"}


@router.get("/audit-log")
async def audit_log(admin: dict = Depends(require_admin)):
    """Return last 100 audit log entries ordered by most recent first."""
    with get_db() as db:
        entries = (
            db.query(AuditLog)
            .order_by(AuditLog.created_at.desc())
            .limit(100)
            .all()
        )
        # Build a lookup of admin emails for user_ids that appear in the log
        admin_ids = {e.user_id for e in entries if e.user_id}
        email_map: dict[str, str] = {}
        if admin_ids:
            admins = db.query(User).filter(User.id.in_(admin_ids)).all()
            email_map = {a.id: a.email for a in admins}

        return [
            {
                "id": e.id,
                "user_id": e.user_id,
                "admin_email": email_map.get(e.user_id),
                "action": e.action,
                "details": e.details,
                "ip_address": e.ip_address,
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ]


# ── Internal helpers ──────────────────────────────────────────────────────

def _ip(request: Request) -> str | None:
    """Extract client IP from request, respecting X-Forwarded-For."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None
