from datetime import datetime, timezone, date, timedelta
from fastapi import APIRouter
from sqlalchemy import func, case, and_
from backend.utils.logger import get_logger
from backend.storage.database import get_db

logger = get_logger(__name__)
router = APIRouter()


def _today_start():
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


@router.get("/daily")
async def daily_analytics():
    from backend.storage.models import Post, Lead, ActionLog
    with get_db() as db:
        today = _today_start()
        # Action counts by type
        rows = (
            db.query(ActionLog.action_type, func.count(ActionLog.id))
            .filter(ActionLog.created_at >= today)
            .group_by(ActionLog.action_type)
            .all()
        )
        stats = {row[0]: row[1] for row in rows}
        posts_scanned = db.query(Post).filter(Post.created_at >= today).count()
        leads_total = db.query(Lead).count()
        emails_found = db.query(Lead).filter(
            Lead.email_status.in_(["FOUND", "VERIFIED"])
        ).count()
    return {
        "date": datetime.now(timezone.utc).date().isoformat(),
        "actions": stats,
        "posts_scanned": posts_scanned,
        "leads_total": leads_total,
        "emails_found": emails_found,
    }


@router.get("/recent-activity")
async def recent_activity(limit: int = 50):
    from backend.storage.models import ActionLog
    with get_db() as db:
        entries = (
            db.query(ActionLog)
            .order_by(ActionLog.created_at.desc())
            .limit(limit)
            .all()
        )
    return [
        {
            "id": e.id,
            "action": e.action_type,
            "target": e.target_name or "",
            "result": e.result or "SUCCESS",
            "comment": e.comment_text,
            "ts": e.created_at.isoformat() if e.created_at else None,
        }
        for e in reversed(entries)
    ]


@router.get("/weekly")
async def weekly_analytics():
    from backend.storage.models import ActionLog, Lead
    with get_db() as db:
        result = []
        for i in range(6, -1, -1):
            day = date.today() - timedelta(days=i)
            day_start = datetime.combine(day, datetime.min.time()).replace(tzinfo=timezone.utc)
            day_end = day_start + timedelta(days=1)

            rows = (
                db.query(ActionLog.action_type, func.count(ActionLog.id))
                .filter(and_(ActionLog.created_at >= day_start, ActionLog.created_at < day_end))
                .group_by(ActionLog.action_type)
                .all()
            )
            actions = {row[0]: row[1] for row in rows}

            leads_found = (
                db.query(Lead)
                .filter(and_(Lead.created_at >= day_start, Lead.created_at < day_end))
                .count()
            )

            result.append({
                "date": day.isoformat(),
                "actions": actions,
                "leads_found": leads_found,
            })
    return result


@router.get("/top-topics")
async def top_topics():
    from backend.storage.models import ActionLog
    with get_db() as db:
        rows = (
            db.query(ActionLog.topic_tag, func.count(ActionLog.id))
            .filter(ActionLog.topic_tag.isnot(None), ActionLog.topic_tag != "")
            .group_by(ActionLog.topic_tag)
            .order_by(func.count(ActionLog.id).desc())
            .limit(10)
            .all()
        )
    return [{"topic": row[0], "count": row[1]} for row in rows]


@router.get("/summary")
async def analytics_summary():
    """Generate a text summary from real stats."""
    from backend.storage.models import ActionLog, Lead, Post
    with get_db() as db:
        week_start = datetime.now(timezone.utc) - timedelta(days=7)

        total_actions = db.query(ActionLog).filter(ActionLog.created_at >= week_start).count()
        total_likes = db.query(ActionLog).filter(
            ActionLog.created_at >= week_start, ActionLog.action_type == "likes"
        ).count()
        total_comments = db.query(ActionLog).filter(
            ActionLog.created_at >= week_start, ActionLog.action_type == "comments"
        ).count()
        total_connections = db.query(ActionLog).filter(
            ActionLog.created_at >= week_start, ActionLog.action_type == "connections"
        ).count()
        posts_scanned = db.query(Post).filter(Post.created_at >= week_start).count()
        new_leads = db.query(Lead).filter(Lead.created_at >= week_start).count()
        emails_found = db.query(Lead).filter(
            Lead.created_at >= week_start,
            Lead.email_status.in_(["FOUND", "VERIFIED"])
        ).count()
        profiles_visited = db.query(Lead).filter(Lead.created_at >= week_start).count()

        # Top topic this week
        top_topic_row = (
            db.query(ActionLog.topic_tag, func.count(ActionLog.id))
            .filter(ActionLog.created_at >= week_start, ActionLog.topic_tag.isnot(None), ActionLog.topic_tag != "")
            .group_by(ActionLog.topic_tag)
            .order_by(func.count(ActionLog.id).desc())
            .first()
        )
        top_topic = top_topic_row[0] if top_topic_row else "N/A"
        top_topic_count = top_topic_row[1] if top_topic_row else 0

    email_rate = f"{round(emails_found / profiles_visited * 100)}%" if profiles_visited > 0 else "N/A"

    summary = (
        f"This week the engine processed {total_actions} engagements "
        f"({total_likes} likes, {total_comments} comments, {total_connections} connections) "
        f"across {posts_scanned} scanned posts. "
    )
    if top_topic != "N/A":
        summary += f"The '{top_topic}' topic drove the most interactions ({top_topic_count} engagements). "
    summary += (
        f"Email enrichment found addresses for {email_rate} of visited profiles, "
        f"adding {new_leads} new leads."
    )

    return {"summary": summary}


@router.get("/campaign-funnel")
async def campaign_funnel():
    from backend.storage.models import CampaignEnrollment
    with get_db() as db:
        enrolled = db.query(CampaignEnrollment).count()
        in_progress = db.query(CampaignEnrollment).filter(
            CampaignEnrollment.status == "IN_PROGRESS"
        ).count()
        completed = db.query(CampaignEnrollment).filter(
            CampaignEnrollment.status == "COMPLETED"
        ).count()
        failed = db.query(CampaignEnrollment).filter(
            CampaignEnrollment.status == "FAILED"
        ).count()
    return {
        "enrolled": enrolled,
        "in_progress": in_progress,
        "completed": completed,
        "failed": failed,
    }


@router.get("/skipped-posts")
async def skipped_posts(limit: int = 50):
    """Return recently skipped posts for FeedEngagement page."""
    from backend.storage.models import Post
    with get_db() as db:
        posts = (
            db.query(Post)
            .filter(Post.state == "SKIPPED")
            .order_by(Post.updated_at.desc())
            .limit(limit)
            .all()
        )
    return [
        {
            "author": p.author_name or "Unknown",
            "snippet": (p.text or "")[:45] + "..." if p.text and len(p.text) > 45 else (p.text or ""),
            "score": p.relevance_score or 0,
            "reason": getattr(p, "skip_reason", None) or f"Score {p.relevance_score or 0} < threshold",
            "time": p.updated_at.isoformat() if p.updated_at else "",
        }
        for p in posts
    ]


@router.get("/acted-posts")
async def acted_posts(limit: int = 50):
    """Return recently acted-on posts for FeedEngagement page."""
    from backend.storage.models import Post
    with get_db() as db:
        posts = (
            db.query(Post)
            .filter(Post.state.in_(["ACTED", "FAILED"]))
            .order_by(Post.updated_at.desc())
            .limit(limit)
            .all()
        )
    return [
        {
            "author": p.author_name or "Unknown",
            "snippet": (p.text or "")[:45] + "..." if p.text and len(p.text) > 45 else (p.text or ""),
            "score": p.relevance_score or 0,
            "action": p.action_taken or "UNKNOWN",
            "result": p.state,
            "time": p.updated_at.isoformat() if p.updated_at else "",
        }
        for p in posts
    ]


@router.get("/comment-history")
async def comment_history(limit: int = 50):
    """Return recent comments for FeedEngagement page."""
    from backend.storage.models import ActionLog
    with get_db() as db:
        entries = (
            db.query(ActionLog)
            .filter(ActionLog.action_type == "comments", ActionLog.comment_text.isnot(None))
            .order_by(ActionLog.created_at.desc())
            .limit(limit)
            .all()
        )
    return [
        {
            "author": e.target_name or "Unknown",
            "comment": e.comment_text or "",
            "link": e.target_url or "#",
            "time": e.created_at.isoformat() if e.created_at else "",
        }
        for e in entries
    ]
