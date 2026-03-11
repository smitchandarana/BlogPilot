from fastapi import APIRouter
from backend.utils.logger import get_logger
from backend.storage.database import get_db
import backend.storage.engagement_log as eng_log

logger = get_logger(__name__)
router = APIRouter()


@router.get("/daily")
async def daily_analytics():
    with get_db() as db:
        stats = eng_log.get_stats_today(db)
    return {
        "date": __import__("datetime").date.today().isoformat(),
        "actions": stats,
        "leads_found": 0,  # TODO: wire to leads_store in Sprint 8
    }


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
