"""Platform database models — PostgreSQL via SQLAlchemy."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Text, Float, JSON,
    ForeignKey, UniqueConstraint, Index, create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from contextlib import contextmanager

from bp_platform.config import DATABASE_URL

Base = declarative_base()

_engine = None
SessionLocal = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(DATABASE_URL, pool_size=5, pool_pre_ping=True)
    return _engine


def _get_session_factory():
    global SessionLocal
    if SessionLocal is None:
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_get_engine())
    return SessionLocal


def init_db():
    Base.metadata.create_all(bind=_get_engine())


@contextmanager
def get_db():
    factory = _get_session_factory()
    session = factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Models ────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), default="")
    role = Column(String(20), default="user")  # user | superuser | admin
    subscription_status = Column(String(20), default="pending")  # pending | active | cancelled | suspended | past_due
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)

    container = relationship("Container", back_populates="user", uselist=False)


class Container(Base):
    __tablename__ = "containers"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    docker_container_id = Column(String(64), nullable=True)
    container_name = Column(String(100), unique=True, nullable=False)
    host_port = Column(Integer, unique=True, nullable=False)
    status = Column(String(20), default="created")  # created | starting | running | stopping | stopped | error | destroyed
    api_token = Column(String(64), nullable=False)
    health_status = Column(String(20), default="unknown")  # healthy | unhealthy | unknown
    health_check_failures = Column(Integer, default=0)
    last_health_check = Column(DateTime, nullable=True)
    engine_state = Column(String(20), nullable=True)
    volume_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    stopped_at = Column(DateTime, nullable=True)
    restart_count = Column(Integer, default=0)
    last_api_call = Column(DateTime, nullable=True)
    linkedin_email = Column(String(255), nullable=True)
    linkedin_password = Column(Text, nullable=True)  # stored as plaintext, never returned via API

    user = relationship("User", back_populates="container")


class BillingEvent(Base):
    __tablename__ = "billing_events"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    stripe_event_id = Column(String(255), unique=True, nullable=True)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=True)
    processed_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_billing_events_user_id", "user_id"),
    )


class PasswordResetToken(Base):
    """DB-persisted password reset tokens — survives server restarts."""
    __tablename__ = "password_reset_tokens"

    token = Column(String(64), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(100), nullable=False)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_audit_log_user_id", "user_id"),
        Index("idx_audit_log_created_at", "created_at"),
    )
