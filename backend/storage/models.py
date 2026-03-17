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
    skip_reason = Column(String(256))
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


class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"

    id = Column(String(64), primary_key=True)
    text = Column(Text, nullable=False)
    topic = Column(String(256))
    style = Column(String(64))
    tone = Column(String(64))
    status = Column(String(32), default="SCHEDULED")  # SCHEDULED | PUBLISHED | FAILED | CANCELLED
    scheduled_at = Column(DateTime, nullable=False)
    published_at = Column(DateTime)
    error_msg = Column(Text)
    created_at = Column(DateTime, default=_utcnow)


class TopicPerformance(Base):
    __tablename__ = "topic_performance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic = Column(String(256), nullable=False, index=True, unique=True)
    hashtag = Column(String(256), nullable=True)
    comments_generated = Column(Integer, default=0)
    likes_given = Column(Integer, default=0)
    avg_score = Column(Float, default=0.0)
    posts_seen = Column(Integer, default=0)
    posts_engaged = Column(Integer, default=0)
    engagement_rate = Column(Float, default=0.0)
    last_used = Column(DateTime, default=_utcnow)
    last_rotated = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    is_paused = Column(Boolean, default=False)
    pause_reason = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=_utcnow)


class CommentQualityLog(Base):
    __tablename__ = "comment_quality_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(String, nullable=False)
    post_text_snippet = Column(String)
    comment_used = Column(Text)
    candidate_count = Column(Integer)
    quality_score = Column(Float)
    angle = Column(String(32))
    got_reply = Column(Boolean, default=False)
    reply_count = Column(Integer, default=0)
    topic = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow)


class PostQualityLog(Base):
    __tablename__ = "post_quality_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic = Column(String)
    style = Column(String)
    post_text = Column(Text)
    quality_score = Column(Float)
    was_published = Column(Boolean, default=False)
    rejection_reason = Column(String, nullable=True)
    likes_received = Column(Integer, default=0)
    comments_received = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)


class ResearchedTopic(Base):
    __tablename__ = "researched_topics"

    id = Column(String(64), primary_key=True)  # UUID
    topic = Column(String(256), nullable=False, index=True)
    domain = Column(String(256), nullable=True, index=True)  # parent broad category
    trending_score = Column(Float, default=0.0)       # 0-10
    engagement_score = Column(Float, default=0.0)      # 0-10
    content_gap_score = Column(Float, default=0.0)     # 0-10
    relevance_score = Column(Float, default=0.0)       # 0-10
    composite_score = Column(Float, default=0.0)       # weighted average
    suggested_angle = Column(Text)
    snippet_count = Column(Integer, default=0)
    status = Column(String(32), default="RESEARCHED")  # RESEARCHED | USED | EXPIRED
    researched_at = Column(DateTime, default=_utcnow)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=_utcnow)


class ResearchSnippet(Base):
    __tablename__ = "research_snippets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic_id = Column(String(64), ForeignKey("researched_topics.id"), nullable=False)
    source = Column(String(32), nullable=False)    # REDDIT | RSS | LINKEDIN | HN
    source_url = Column(String(2048))
    title = Column(String(512))
    snippet = Column(Text)
    engagement_signal = Column(Integer, default=0)  # upvotes/likes/comments
    discovered_at = Column(DateTime, default=_utcnow)
    processed_for_insights = Column(Boolean, default=False)


class PostContentHash(Base):
    __tablename__ = "post_content_hashes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_hash = Column(String(64), unique=True, nullable=False)  # SHA256 of normalized text
    post_id = Column(String(64))           # FK to scheduled_posts.id
    text_preview = Column(String(500))     # first 500 chars for debugging
    created_at = Column(DateTime, default=_utcnow)


class GenerationSession(Base):
    """Tracks each structured post generation — inputs, outputs, edits, final action."""
    __tablename__ = "generation_sessions"

    id = Column(String(64), primary_key=True)      # UUID
    topic = Column(String(256))
    subtopic = Column(String(256))
    audience = Column(String(256))
    pain_point = Column(Text)
    hook_intent = Column(String(32))               # CONTRARIAN | QUESTION | STAT | STORY | TREND | MISTAKE
    proof_type = Column(String(32))
    style = Column(String(64))
    tone = Column(String(64))
    generated_text = Column(Text)                  # raw output from Groq
    final_text = Column(Text)                      # text user actually published (may differ)
    quality_score = Column(Float, default=0.0)
    edit_distance_ratio = Column(Float, default=0.0)  # 0=unchanged, 1=completely rewritten
    action = Column(String(32), default="pending")    # pending | published | discarded | scheduled
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)


class ContentInsight(Base):
    """Structured AI-extracted insights from research snippets."""
    __tablename__ = "content_insights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snippet_id = Column(Integer, ForeignKey("research_snippets.id"), nullable=True)
    topic = Column(String(256))
    subtopic = Column(String(256))
    pain_point = Column(String(512))
    hook_type = Column(String(64))         # CONTRARIAN | QUESTION | STAT | STORY | TREND | MISTAKE
    content_style = Column(String(64))     # TACTICAL | STRATEGIC | PERSONAL | EDUCATIONAL | PROVOCATIVE
    key_insight = Column(Text)
    audience_segment = Column(String(128))
    sentiment = Column(String(32))         # POSITIVE | NEGATIVE | NEUTRAL | MIXED
    specificity_score = Column(Float, default=0.0)
    source_engagement = Column(Integer, default=0)
    source_type = Column(String(32))       # REDDIT | RSS | HN | LINKEDIN | MANUAL
    times_used_in_generation = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)


class ContentPattern(Base):
    """Aggregated recurring patterns computed from content_insights."""
    __tablename__ = "content_patterns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pattern_type = Column(String(64), nullable=False)  # PAIN_POINT | HOOK | AUDIENCE | TOPIC_TREND
    pattern_value = Column(String(512), nullable=False)
    frequency = Column(Integer, default=1)
    avg_engagement = Column(Float, default=0.0)
    example_insight_ids = Column(JSON, default=list)
    domain = Column(String(256), nullable=True)
    first_seen_at = Column(DateTime, default=_utcnow)
    last_seen_at = Column(DateTime, default=_utcnow)
    created_at = Column(DateTime, default=_utcnow)
