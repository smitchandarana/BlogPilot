from datetime import datetime, timezone
from fastapi import APIRouter
from backend.utils.logger import get_logger
from backend.storage.database import get_db
import backend.storage.engagement_log as eng_log

logger = get_logger(__name__)
router = APIRouter()


def _today_start():
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


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
    from datetime import date, timedelta
    result = []
    for i in range(6, -1, -1):
        day = date.today() - timedelta(days=i)
        result.append({
            "date": day.isoformat(),
            "actions": {},
            "leads_found": 0,
        })
    return result


@router.get("/top-topics")
async def top_topics():
    return []


@router.get("/summary")
async def analytics_summary():
    return {"summary": "Summary coming soon"}


@router.get("/campaign-funnel")
async def campaign_funnel():
    return {
        "enrolled": 0,
        "connected": 0,
        "replied": 0,
        "converted": 0,
    }
