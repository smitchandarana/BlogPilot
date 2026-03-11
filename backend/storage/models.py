import hashlib
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Text, JSON, Boolean, ForeignKey
)
from backend.storage.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Post(Base):
    __tablename__ = "posts"

    id = Column(String(64), primary_key=True)  # SHA256 of URL
    url = Column(String(2048), unique=True, nullable=False)
    author_name = Column(String(256))
    author_url = Column(String(2048))
    text = Column(Text)
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    relevance_score = Column(Float, default=0.0)
    state = Column(String(32), default="SEEN")  # SEEN | SCORED | ACTED | SKIPPED | FAILED
    action_taken = Column(String(32))            # LIKE | COMMENT | CONNECT | SKIP
    comment_text = Column(Text)
    topic_tag = Column(String(128))
    post_timestamp = Column(DateTime)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    def __init__(self, url: str, **kwargs):
        self.id = hashlib.sha256(url.encode()).hexdigest()
        self.url = url
        for k, v in kwargs.items():
            setattr(self, k, v)


class Lead(Base):
    __tablename__ = "leads"

    id = Column(String(64), primary_key=True)  # SHA256 of linkedin_url
    linkedin_url = Column(String(2048), unique=True, nullable=False)
    first_name = Column(String(128))
    last_name = Column(String(128))
    title = Column(String(256))
    company = Column(String(256))
    company_domain = Column(String(256))
    email = Column(String(256))
    email_status = Column(String(32), default="NOT_FOUND")  # NOT_FOUND | FOUND | VERIFIED | BOUNCED
    email_method = Column(String(32))                        # DOM | HUNTER | PATTERN | SMTP
    connection_degree = Column(Integer)
    source = Column(String(128))
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    def __init__(self, linkedin_url: str, **kwargs):
        self.id = hashlib.sha256(linkedin_url.encode()).hexdigest()
        self.linkedin_url = linkedin_url
        for k, v in kwargs.items():
            setattr(self, k, v)


class ActionLog(Base):
    __tablename__ = "actions_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action_type = Column(String(32), nullable=False)  # LIKE | COMMENT | CONNECT | VISIT | ...
    target_url = Column(String(2048))
    target_name = Column(String(256))
    result = Column(String(32))                        # SUCCESS | FAILED | SKIPPED
    comment_text = Column(Text)
    error_msg = Column(Text)
    topic_tag = Column(String(128))
    created_at = Column(DateTime, default=_utcnow)


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(String(64), primary_key=True)
    name = Column(String(256), nullable=False)
    status = Column(String(32), default="ACTIVE")  # ACTIVE | PAUSED | ARCHIVED
    steps = Column(JSON, default=list)             # List of step configs
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class CampaignEnrollment(Base):
    __tablename__ = "campaign_enrollments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(String(64), ForeignKey("campaigns.id"), nullable=False)
    lead_id = Column(String(64), ForeignKey("leads.id"), nullable=False)
    status = Column(String(32), default="IN_PROGRESS")  # IN_PROGRESS | COMPLETED | FAILED | PAUSED
    current_step = Column(Integer, default=0)
    next_action_at = Column(DateTime, default=_utcnow)
    enrolled_at = Column(DateTime, default=_utcnow)
    completed_at = Column(DateTime)


class Budget(Base):
    __tablename__ = "budget"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action_type = Column(String(64), unique=True, nullable=False)
    limit_per_day = Column(Integer, default=0)  # 0 = unlimited
    count_today = Column(Integer, default=0)
    last_reset_at = Column(DateTime, default=_utcnow)


class Settings(Base):
    __tablename__ = "settings"

    key = Column(String(256), primary_key=True)
    value = Column(Text)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
