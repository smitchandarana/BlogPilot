"""Platform health endpoints."""

from fastapi import APIRouter
from sqlalchemy import text

from platform.models.database import User, Container, get_db

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
