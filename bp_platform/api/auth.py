"""Platform authentication — signup, login, JWT, password reset, account management."""

import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.exc import IntegrityError
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

from bp_platform.models.database import User, Container, PasswordResetToken, get_db
from bp_platform.services.token_service import (
    hash_password, verify_password, create_jwt, decode_jwt,
)
from bp_platform.config import REQUIRE_SIGNUP_APPROVAL, APP_BASE_URL


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
    pending_approval: bool = False
    message: str | None = None


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
    req.email = req.email.lower().strip()
    with get_db() as db:
        existing = db.query(User).filter_by(email=req.email).first()
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")

        if REQUIRE_SIGNUP_APPROVAL:
            # Pending approval mode — account is inactive until admin approves
            user = User(
                email=req.email,
                password_hash=hash_password(req.password),
                name=req.name,
                role="user",
                subscription_status="pending",
                is_active=False,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            # Issue a token so the client can show a proper pending screen,
            # but the account is blocked at get_current_user until approved.
            token = create_jwt(user.id, user.email, user.role)
            return TokenResponse(
                token=token,
                user_id=user.id,
                email=user.email,
                role=user.role,
                name=user.name,
                pending_approval=True,
                message="Account pending admin approval. You will be notified once your account is activated.",
            )
        else:
            user = User(
                email=req.email,
                password_hash=hash_password(req.password),
                name=req.name,
                role="user",
                subscription_status="active",
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
        user = db.query(User).filter_by(email=req.email.lower().strip()).first()
        # Always run verify_password to prevent user-enumeration via timing
        _dummy = "$2b$12$LQv3c1yqBwEHxPu0r2JxmOzJ7CgqkFqKcEf8b6Lv4mXJuRZ2iYbCe"
        password_ok = verify_password(req.password, user.password_hash if user else _dummy)
        if not user or not password_ok:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if not user.is_active:
            # Distinguish pending from suspended for better UX
            if user.subscription_status == "pending":
                raise HTTPException(
                    status_code=403,
                    detail="Account pending admin approval. Please wait for activation."
                )
            raise HTTPException(status_code=403, detail="Account suspended")

        # Get container info if exists
        container = db.query(Container).filter_by(user_id=user.id).first()
        c_port = container.host_port if container else None
        c_status = container.status if container else None
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
            container_port=c_port,
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
            container_port=port,
            container_status=c_status,
            container_token=c_token,
        )


# ── Password Reset ────────────────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post("/forgot-password")
@limiter.limit("3/minute")
async def forgot_password(request: Request, req: ForgotPasswordRequest):
    """Generate a DB-persisted password reset token. In production, email this to the user."""
    with get_db() as db:
        u = db.query(User).filter_by(email=req.email.lower().strip()).first()
        # Always return success (don't leak whether email exists)
        if u:
            # Invalidate any existing unused tokens for this user
            db.query(PasswordResetToken).filter_by(user_id=u.id, used=False).delete()
            reset_token = secrets.token_urlsafe(32)
            db.add(PasswordResetToken(
                token=reset_token,
                user_id=u.id,
                expires_at=datetime.utcnow() + timedelta(hours=1),
            ))
            db.commit()
            reset_link = f"{APP_BASE_URL}/reset-password?token={reset_token}"
            import logging
            logging.getLogger("bp_platform").info(f"[DEV] Password reset link for {req.email}: {reset_link}")
    return {"message": "If that email exists, a reset link has been sent."}


@router.post("/reset-password")
@limiter.limit("5/minute")
async def reset_password(request: Request, req: ResetPasswordRequest):
    """Reset password using a valid token."""
    if len(req.new_password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")
    with get_db() as db:
        entry = db.query(PasswordResetToken).filter_by(token=req.token, used=False).first()
        if not entry or entry.expires_at < datetime.utcnow():
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")
        u = db.query(User).filter_by(id=entry.user_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="User not found")
        u.password_hash = hash_password(req.new_password)
        entry.used = True
        db.commit()
        # Prune expired and used tokens to prevent table bloat
        db.query(PasswordResetToken).filter(
            PasswordResetToken.expires_at < datetime.utcnow()
        ).delete()
        db.commit()
    return {"message": "Password reset successful. You can now log in."}


# ── Account Management ────────────────────────────────────────────────────

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ChangeEmailRequest(BaseModel):
    password: str
    new_email: EmailStr


@router.post("/change-password")
async def change_password(req: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    if len(req.new_password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")
    with get_db() as db:
        u = db.query(User).filter_by(id=user["sub"]).first()
        if not u or not verify_password(req.current_password, u.password_hash):
            raise HTTPException(status_code=401, detail="Current password is incorrect")
        u.password_hash = hash_password(req.new_password)
        db.commit()
    return {"message": "Password changed successfully"}


@router.post("/change-email")
async def change_email(req: ChangeEmailRequest, user: dict = Depends(get_current_user)):
    new_email = req.new_email.lower().strip()
    with get_db() as db:
        u = db.query(User).filter_by(id=user["sub"]).first()
        if not u or not verify_password(req.password, u.password_hash):
            raise HTTPException(status_code=401, detail="Password is incorrect")
        existing = db.query(User).filter_by(email=new_email).first()
        if existing:
            raise HTTPException(status_code=409, detail="Email already in use")
        u.email = new_email
        u.updated_at = datetime.utcnow()
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="Email already in use")
    return {"message": "Email updated successfully"}


@router.delete("/account")
async def delete_account(user: dict = Depends(get_current_user)):
    """Self-service account deletion. Stops and destroys container + data."""
    import asyncio
    user_id = user["sub"]
    # Stop and destroy container (blocking Docker call — run in thread).
    # Log failures but always proceed — users must be able to delete their account
    # even if Docker is temporarily unavailable (resource orphan is preferable to
    # account deletion being permanently blocked).
    try:
        from bp_platform.services import container_manager
        await asyncio.to_thread(container_manager.destroy_container, user_id, True)
    except Exception as _e:
        import logging
        logging.getLogger("bp_platform").error(
            f"delete_account: container cleanup failed for {user_id}: {_e} — proceeding with account deletion"
        )
    # Delete user record (cascades to container record)
    with get_db() as db:
        u = db.query(User).filter_by(id=user_id).first()
        if u:
            db.delete(u)
            db.commit()
    return {"message": "Account deleted"}
