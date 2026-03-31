"""BlogPilot Platform API — manages multi-tenant container lifecycle."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from platform.config import ADMIN_EMAIL, ADMIN_PASSWORD
from platform.models.database import init_db, get_db, User
from platform.services.token_service import hash_password
from platform.services.health_monitor import health_monitor_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("platform")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Boot ──────────────────────────────────────────────────────────
    logger.info("Platform API booting...")

    # Init database tables
    init_db()
    logger.info("Platform database initialised")

    # Bootstrap admin user if not exists
    _bootstrap_admin()

    # Start health monitor background task
    monitor_task = asyncio.create_task(health_monitor_loop())
    logger.info("Health monitor started")

    logger.info("Platform API ready")
    yield

    # ── Shutdown ──────────────────────────────────────────────────────
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass
    logger.info("Platform API shutdown")


app = FastAPI(
    title="BlogPilot Platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://app.phoenixsolution.in",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Register routers
from platform.api.auth import router as auth_router
from platform.api.containers import router as containers_router
from platform.api.admin import router as admin_router
from platform.api.billing import router as billing_router
from platform.api.health import router as health_router

app.include_router(auth_router)
app.include_router(containers_router)
app.include_router(admin_router)
app.include_router(billing_router)
app.include_router(health_router)


def _bootstrap_admin():
    """Create admin user on first boot if not exists."""
    with get_db() as db:
        existing = db.query(User).filter_by(email=ADMIN_EMAIL).first()
        if existing:
            return
        admin = User(
            email=ADMIN_EMAIL,
            password_hash=hash_password(ADMIN_PASSWORD),
            name="Admin",
            role="admin",
            subscription_status="active",
            is_active=True,
        )
        db.add(admin)
        db.commit()
        logger.info(f"Admin user created: {ADMIN_EMAIL}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("platform.main:app", host="0.0.0.0", port=9000, reload=True)
