"""
Comment monitor — Phase C1.

Scheduler job that revisits posts where we commented, checks if our
comment got a reply, and updates CommentQualityLog with engagement data.

This closes the feedback loop: generate comment → post it → check for replies
→ learn which angles/styles get responses.
"""
import asyncio
from datetime import datetime, timedelta

from backend.utils.config_loader import get as cfg_get
from backend.utils.logger import get_logger

logger = get_logger(__name__)


async def check_comment_replies() -> int:
    """
    Revisit recent posts where we commented and check for replies.

    Returns the number of comments updated.
    """
    from backend.storage.database import get_db
    from backend.storage.models import CommentQualityLog
    from backend.automation.browser import BrowserManager
    from backend.automation.linkedin_login import LinkedInLogin
    from backend.automation.human_behavior import random_delay

    lookback_hours = int(cfg_get("learning.comment_monitor_lookback_hours", 48))
    max_per_check = int(cfg_get("learning.comment_monitor_max_per_check", 10))
    cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)  # naive — matches SQLite storage

    with get_db() as db:
        # Find comments that haven't been checked for replies yet
        rows = (
            db.query(CommentQualityLog)
            .filter(
                CommentQualityLog.got_reply.is_(None),
                CommentQualityLog.created_at >= cutoff,
            )
            .order_by(CommentQualityLog.created_at.desc())
            .limit(max_per_check)
            .all()
        )

    if not rows:
        logger.info("CommentMonitor: no unchecked comments to review")
        return 0

    logger.info(f"CommentMonitor: checking {len(rows)} comments for replies")

    browser = BrowserManager()
    updated = 0

    try:
        await browser.launch()
        page = await browser.get_page()

        login = LinkedInLogin()
        if not await login.is_logged_in(page):
            ok = await login.login(page)
            if not ok:
                logger.warning("CommentMonitor: login failed — aborting")
                return 0

        for row in rows:
            try:
                reply_count = await _count_replies_on_post(
                    page, row.post_id, row.comment_used
                )
                got_reply = reply_count > 0

                with get_db() as db:
                    from backend.storage import quality_log
                    quality_log.update_comment_engagement(
                        db, row.id, got_reply, reply_count
                    )

                if got_reply:
                    logger.info(
                        f"CommentMonitor: comment {row.id} got {reply_count} reply(ies)"
                    )
                updated += 1

                await random_delay(3.0, 8.0)

            except Exception as e:
                logger.debug(f"CommentMonitor: error checking comment {row.id}: {e}")
                continue

    finally:
        await browser.close()

    logger.info(f"CommentMonitor: updated {updated} comments")
    return updated


async def _count_replies_on_post(page, post_url: str, our_comment: str) -> int:
    """
    Navigate to a post, find our comment, count replies beneath it.
    Returns 0 if our comment is not found or has no replies.
    """
    try:
        await page.goto(post_url, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(2.0)

        # Expand comments if needed
        show_comments = await page.query_selector(
            "button[aria-label*='comment' i], "
            "button:text-is('Show comments')"
        )
        if show_comments:
            await show_comments.click()
            await asyncio.sleep(1.5)

        # Find all comment elements
        comments = await page.query_selector_all(
            "article.comments-comment-item, "
            "div.comments-comment-item"
        )

        # Search for our comment by matching text content
        our_text_lower = (our_comment or "").lower().strip()[:50]
        if not our_text_lower:
            return 0

        for comment_el in comments:
            text_el = await comment_el.query_selector(
                "span.comments-comment-item__main-content, "
                "div.comments-comment-item__inline-show-more-text"
            )
            if not text_el:
                continue

            text = (await text_el.inner_text()).strip().lower()
            if our_text_lower in text:
                # Found our comment — count replies
                reply_els = await comment_el.query_selector_all(
                    "article.comments-comment-item__reply, "
                    "div.comments-reply-item"
                )
                return len(reply_els)

        return 0
    except Exception as e:
        logger.debug(f"CommentMonitor: reply count error: {e}")
        return 0


def run_comment_monitor():
    """Sync entry point called by scheduler."""
    logger.info("CommentMonitor: scheduled check starting")
    try:
        count = asyncio.run(check_comment_replies())
        logger.info(f"CommentMonitor: check complete — {count} comments updated")
    except Exception as e:
        logger.warning(f"CommentMonitor: check failed: {e}")
