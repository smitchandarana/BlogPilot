"""
Content Studio API — Sprint 7.

Endpoints for the ContentStudio page:
  POST /content/schedule     — queue a post for publishing at a future time
  POST /content/publish-now  — publish immediately via browser
  GET  /content/queue        — list all scheduled/published posts
  DELETE /content/queue/{id} — cancel a scheduled post
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.utils.logger import get_logger
from backend.storage.database import get_db
from backend.storage.models import ScheduledPost

logger = get_logger(__name__)
router = APIRouter()


# ── Request / response models ─────────────────────────────────────────────

class ScheduleRequest(BaseModel):
    text: str
    topic: Optional[str] = None
    style: Optional[str] = None
    tone: Optional[str] = None
    scheduled_at: str  # ISO 8601 string, e.g. "2025-06-01T09:00:00"


class PublishNowRequest(BaseModel):
    text: str
    topic: Optional[str] = None
    style: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("/queue")
async def get_post_queue():
    """Return all posts in the schedule queue (any status)."""
    with get_db() as db:
        posts = (
            db.query(ScheduledPost)
            .order_by(ScheduledPost.scheduled_at.asc())
            .all()
        )
        return [_serialize(p) for p in posts]


@router.post("/schedule")
async def schedule_post(body: ScheduleRequest, force: bool = Query(False)):
    """Add a post to the publishing queue at the given scheduled_at time."""
    try:
        scheduled_at = datetime.fromisoformat(body.scheduled_at)
        if scheduled_at.tzinfo is None:
            scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid scheduled_at format — use ISO 8601")

    # Duplicate detection
    if not force:
        try:
            from backend.research.duplicate_detector import check_duplicate
            with get_db() as db:
                dup = check_duplicate(body.text, db)
                if dup["is_duplicate"]:
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "message": "Near-duplicate post detected",
                            "similarity": dup["similarity"],
                            "matching_preview": dup["matching_preview"],
                        },
                    )
        except HTTPException:
            raise
        except Exception:
            pass  # Don't block on duplicate check failure

    with get_db() as db:
        post = ScheduledPost(
            id=str(uuid.uuid4()),
            text=body.text,
            topic=body.topic,
            style=body.style,
            tone=body.tone,
            status="SCHEDULED",
            scheduled_at=scheduled_at,
        )
        db.add(post)
        db.commit()
        db.refresh(post)
        logger.info(f"Content: post scheduled for {scheduled_at.isoformat()}")
        return _serialize(post)


@router.delete("/queue/{post_id}")
async def cancel_post(post_id: str):
    """Cancel a scheduled post (only if still in SCHEDULED status)."""
    with get_db() as db:
        post = db.query(ScheduledPost).filter_by(id=post_id).first()
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        if post.status != "SCHEDULED":
            raise HTTPException(
                status_code=409,
                detail=f"Cannot cancel post with status '{post.status}'"
            )
        post.status = "CANCELLED"
        db.commit()
        logger.info(f"Content: post {post_id} cancelled")
        return {"cancelled": post_id}


@router.post("/publish-now")
async def publish_now(body: PublishNowRequest, force: bool = Query(False)):
    """
    Immediately publish a post via the LinkedIn browser session.
    This runs synchronously (via asyncio) — may take 10-30 seconds.
    """
    from backend.core.engine import get_engine
    from backend.core.state_manager import EngineState

    engine = get_engine()
    if not engine or engine.state_manager.get() != EngineState.RUNNING:
        raise HTTPException(
            status_code=409,
            detail="Engine must be RUNNING to publish a post"
        )

    # Duplicate detection
    if not force:
        try:
            from backend.research.duplicate_detector import check_duplicate
            with get_db() as db:
                dup = check_duplicate(body.text, db)
                if dup["is_duplicate"]:
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "message": "Near-duplicate post detected",
                            "similarity": dup["similarity"],
                            "matching_preview": dup["matching_preview"],
                        },
                    )
        except HTTPException:
            raise
        except Exception:
            pass

    # Record the post in DB as a scheduled post with now as scheduled_at
    with get_db() as db:
        post = ScheduledPost(
            id=str(uuid.uuid4()),
            text=body.text,
            topic=body.topic,
            style=body.style,
            status="SCHEDULED",
            scheduled_at=datetime.now(timezone.utc),
        )
        db.add(post)
        db.commit()
        post_id = post.id

    # Submit to worker pool so it runs off the request thread
    engine.worker_pool.submit(_publish_single, post_id, body.text)
    logger.info(f"Content: publish-now submitted for post {post_id}")
    return {"status": "queued", "post_id": post_id}


# ── Internal helpers ──────────────────────────────────────────────────────

def _serialize(post: ScheduledPost) -> dict:
    return {
        "id": post.id,
        "text": post.text,
        "topic": post.topic,
        "style": post.style,
        "tone": post.tone,
        "status": post.status,
        "scheduled_at": post.scheduled_at.isoformat() if post.scheduled_at else None,
        "published_at": post.published_at.isoformat() if post.published_at else None,
        "error_msg": post.error_msg,
        "created_at": post.created_at.isoformat() if post.created_at else None,
    }


def _publish_single(post_id: str, text: str) -> None:
    """Sync wrapper — called by worker pool to publish one post."""
    import asyncio
    try:
        asyncio.run(_async_publish(post_id, text))
    except Exception as e:
        logger.error(f"Content: publish_single failed — {e}", exc_info=True)


async def _async_publish(post_id: str, text: str) -> None:
    """Async: open browser, login, publish, update DB."""
    from backend.automation.browser import BrowserManager
    from backend.automation.linkedin_login import LinkedInLogin
    from backend.automation.post_publisher import PostPublisher
    from backend.storage.database import get_db as _get_db

    browser = BrowserManager()
    try:
        await browser.launch()
        page = await browser.get_page()

        login = LinkedInLogin()
        if not await login.is_logged_in(page):
            ok = await login.login(page)
            if not ok:
                _mark_failed(post_id, "Login failed")
                return

        publisher = PostPublisher()
        success = await publisher.publish(page, text)

        with _get_db() as db:
            post = db.query(ScheduledPost).filter_by(id=post_id).first()
            if post:
                if success:
                    post.status = "PUBLISHED"
                    post.published_at = datetime.now(timezone.utc)
                    logger.info(f"Content: post {post_id} published successfully")
                else:
                    post.status = "FAILED"
                    post.error_msg = "Publisher returned False"
                    logger.error(f"Content: post {post_id} failed to publish")
                db.commit()

        # Register content hash for duplicate detection
        if success:
            try:
                from backend.research.duplicate_detector import register_post
                with _get_db() as db_dup:
                    register_post(text, post_id, db_dup)
            except Exception:
                pass

        # Post quality logging for self-learning
        if success:
            try:
                from backend.storage import quality_log
                with _get_db() as db_ql:
                    quality_log.log_post(
                        db=db_ql,
                        topic=post.topic if post else "",
                        style=post.style if post else "",
                        post_text=text,
                        quality_score=0.0,  # score not available at publish time
                        was_published=True,
                    )
            except Exception:
                pass

        # Budget tracking
        if success:
            try:
                from backend.storage.database import get_db as _get_db2
                from backend.storage import budget_tracker
                with _get_db2() as db2:
                    budget_tracker.increment("posts_published", db2)
            except Exception:
                pass

        # WebSocket notification
        try:
            from backend.api.websocket import schedule_broadcast
            schedule_broadcast("activity", {
                "action": "POST_PUBLISHED",
                "target": "LinkedIn Feed",
                "result": "SUCCESS" if success else "FAILED",
            })
        except Exception:
            pass

    finally:
        await browser.close()


def _mark_failed(post_id: str, reason: str) -> None:
    try:
        from backend.storage.database import get_db as _get_db
        with _get_db() as db:
            post = db.query(ScheduledPost).filter_by(id=post_id).first()
            if post:
                post.status = "FAILED"
                post.error_msg = reason
                db.commit()
    except Exception as e:
        logger.warning(f"Content: could not mark post {post_id} failed — {e}")
