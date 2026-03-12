from datetime import datetime, timezone, date, timedelta
from fastapi import APIRouter
from sqlalchemy import func, cast, Date
from backend.utils.logger import get_logger
from backend.storage.database import get_db
import backend.storage.engagement_log as eng_log

logger = get_logger(__name__)
router = APIRouter()


def _today_start():
    return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)


@router.get("/daily")
async def daily_analytics():
    from backend.storage.models import Post, Lead
    with get_db() as db:
        stats = eng_log.get_stats_today(db)
        today = _today_start()
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
    with get_db() as db:
        entries = eng_log.get_recent(limit, db)
        result = [
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
    return result


@router.get("/weekly")
async def weekly_analytics():
    from backend.storage.models import ActionLog, Lead
    result = []
    with get_db() as db:
        for i in range(6, -1, -1):
            day = date.today() - timedelta(days=i)
            day_start = datetime.combine(day, datetime.min.time())
            day_end = day_start + timedelta(days=1)

            rows = (
                db.query(ActionLog.action_type, func.count(ActionLog.id))
                .filter(ActionLog.created_at >= day_start, ActionLog.created_at < day_end)
                .group_by(ActionLog.action_type)
                .all()
            )
            actions = {row[0]: row[1] for row in rows}

            leads_found = db.query(Lead).filter(
                Lead.created_at >= day_start,
                Lead.created_at < day_end,
            ).count()

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
    from backend.storage.models import ActionLog, Lead, Post
    with get_db() as db:
        today = _today_start()
        week_start = today - timedelta(days=7)

        total_actions = db.query(ActionLog).filter(ActionLog.created_at >= week_start).count()
        likes = db.query(ActionLog).filter(
            ActionLog.created_at >= week_start, ActionLog.action_type == "likes"
        ).count()
        comments = db.query(ActionLog).filter(
            ActionLog.created_at >= week_start, ActionLog.action_type == "comments"
        ).count()
        new_leads = db.query(Lead).filter(Lead.created_at >= week_start).count()
        emails_found = db.query(Lead).filter(
            Lead.created_at >= week_start,
            Lead.email_status.in_(["FOUND", "VERIFIED"]),
        ).count()
        posts_scanned = db.query(Post).filter(Post.created_at >= week_start).count()

        # Build summary text from real data
        parts = []
        if total_actions > 0:
            parts.append(f"This week the engine performed {total_actions} engagements ({likes} likes, {comments} comments).")
        else:
            parts.append("No engagement activity this week.")
        if posts_scanned > 0:
            parts.append(f"{posts_scanned} posts were scanned.")
        if new_leads > 0:
            parts.append(f"{new_leads} new leads were captured.")
        if emails_found > 0:
            parts.append(f"Email enrichment found addresses for {emails_found} leads.")

        summary = " ".join(parts) if parts else "No data available yet. Start the engine to begin collecting analytics."

    return {"summary": summary}


@router.get("/feed-posts")
async def feed_posts(limit: int = 30):
    from backend.storage.models import Post
    with get_db() as db:
        posts = (
            db.query(Post)
            .filter(Post.state.in_(["ACTED", "SCORED", "FAILED"]))
            .order_by(Post.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "author": p.author_name or "Unknown",
                "snippet": (p.text or "")[:45] + ("…" if p.text and len(p.text) > 45 else ""),
                "score": p.relevance_score or 0,
                "action": p.action_taken or "—",
                "result": "SUCCESS" if p.state == "ACTED" else p.state or "—",
                "time": p.created_at.isoformat() if p.created_at else None,
            }
            for p in posts
        ]


@router.get("/feed-skipped")
async def feed_skipped(limit: int = 30):
    from backend.storage.models import Post
    with get_db() as db:
        posts = (
            db.query(Post)
            .filter(Post.state == "SKIPPED")
            .order_by(Post.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "author": p.author_name or "Unknown",
                "snippet": (p.text or "")[:45] + ("…" if p.text and len(p.text) > 45 else ""),
                "score": p.relevance_score or 0,
                "reason": f"Score too low ({p.relevance_score or 0})" if (p.relevance_score or 0) < 6 else "Skipped",
                "time": p.created_at.isoformat() if p.created_at else None,
            }
            for p in posts
        ]


@router.get("/comment-history")
async def comment_history(limit: int = 30):
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
                "time": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ]


@router.get("/comment-quality")
async def comment_quality():
    from backend.storage.quality_log import get_comment_quality_stats
    with get_db() as db:
        return get_comment_quality_stats(db)


@router.get("/post-quality")
async def post_quality():
    from backend.storage.quality_log import get_post_quality_stats
    with get_db() as db:
        return get_post_quality_stats(db)


@router.get("/campaign-funnel")
async def campaign_funnel():
    from backend.storage.models import CampaignEnrollment
    with get_db() as db:
        enrolled = db.query(CampaignEnrollment).count()
        in_progress = db.query(CampaignEnrollment).filter_by(status="IN_PROGRESS").count()
        completed = db.query(CampaignEnrollment).filter_by(status="COMPLETED").count()
        # "connected" approximated as those past step 1
        connected = db.query(CampaignEnrollment).filter(CampaignEnrollment.current_step > 0).count()

    return {
        "enrolled": enrolled,
        "connected": connected,
        "replied": 0,  # no reply tracking yet
        "completed": completed,
    }
