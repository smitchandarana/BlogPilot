"""Platform authentication — signup, login, JWT."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, EmailStr
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

from bp_platform.models.database import User, Container, get_db
from bp_platform.services.token_service import (
    hash_password, verify_password, create_jwt, decode_jwt,
)

router = APIRouter(prefix="/platform/auth", tags=["auth"])


# ── Schemas ───────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    email: EmailStr
    password: str  # min 8 chars enforced in endpoint
    name: str = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    token: str
    user_id: str
    email: str
    role: str
    name: str
    container_port: int | None = None
    container_status: str | None = None
    container_token: str | None = None


class UserProfile(BaseModel):
    id: str
    email: str
    name: str
    role: str
    subscription_status: str
    created_at: str


# ── Auth dependency ───────────────────────────────────────────────────────

def get_current_user(request: Request) -> dict:
    """Extract and validate JWT from Authorization header. Also checks user is still active."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        payload = decode_jwt(auth[7:])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    # Verify user is still active (prevents suspended users from using old tokens)
    with get_db() as db:
        u = db.query(User).filter_by(id=payload["sub"]).first()
        if not u or not u.is_active:
            raise HTTPException(status_code=403, detail="Account suspended or deleted")
    return payload


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.post("/signup", response_model=TokenResponse)
@limiter.limit("3/10minutes")
async def signup(request: Request, req: SignupRequest):
    if len(req.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")
    if len(req.name) > 100:
        raise HTTPException(status_code=422, detail="Name too long (max 100 characters)")
    with get_db() as db:
        existing = db.query(User).filter_by(email=req.email).first()
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")

        user = User(
            email=req.email,
            password_hash=hash_password(req.password),
            name=req.name,
            role="user",
            subscription_status="pending",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        token = create_jwt(user.id, user.email, user.role)
        return TokenResponse(
            token=token,
            user_id=user.id,
            email=user.email,
            role=user.role,
            name=user.name,
        )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(request: Request, req: LoginRequest):
    with get_db() as db:
        user = db.query(User).filter_by(email=req.email).first()
        if not user or not verify_password(req.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account suspended")

        # Get container info if exists
        container = db.query(Container).filter_by(user_id=user.id).first()
        c_status = container.status if container else None
        # Container token returned only at provision time, not on every login
        c_token = container.api_token if container else None

        user.last_login_at = datetime.utcnow()
        db.commit()

        token = create_jwt(user.id, user.email, user.role)
        return TokenResponse(
            token=token,
            user_id=user.id,
            email=user.email,
            role=user.role,
            name=user.name,
            container_status=c_status,
            container_token=c_token,
        )


@router.get("/me", response_model=UserProfile)
async def me(user: dict = Depends(get_current_user)):
    with get_db() as db:
        u = db.query(User).filter_by(id=user["sub"]).first()
        if not u:
            raise HTTPException(status_code=404, detail="User not found")
        return UserProfile(
            id=u.id,
            email=u.email,
            name=u.name,
            role=u.role,
            subscription_status=u.subscription_status,
            created_at=u.created_at.isoformat(),
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(user: dict = Depends(get_current_user)):
    with get_db() as db:
        u = db.query(User).filter_by(id=user["sub"]).first()
        if not u:
            raise HTTPException(status_code=404, detail="User not found")
        container = db.query(Container).filter_by(user_id=u.id).first()
        port = container.host_port if container else None
        c_status = container.status if container else None
        c_token = container.api_token if container else None

        token = create_jwt(u.id, u.email, u.role)
        return TokenResponse(
            token=token,
            user_id=u.id,
            email=u.email,
            role=u.role,
            name=u.name,
            container_status=c_status,
            container_token=c_token,
        )
