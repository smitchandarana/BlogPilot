"""
Quality logging — track comment and post quality metrics.

Usage:
    from backend.storage.quality_log import log_comment, log_post, get_comment_quality_stats
"""
from sqlalchemy import func
from backend.storage.models import CommentQualityLog, PostQualityLog
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def log_comment(db, post_id, post_text, comment_used, quality_score,
                candidate_count, topic, all_candidates, angle="unknown"):
    """Insert a new CommentQualityLog row. Returns the created row or None."""
    try:
        row = CommentQualityLog(
            post_id=post_id,
            post_text_snippet=post_text[:200] if post_text else "",
            comment_used=comment_used,
            candidate_count=candidate_count,
            quality_score=quality_score,
            angle=angle,
            topic=topic,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    except Exception as e:
        logger.error(f"log_comment failed: {e}")
        db.rollback()
        return None


def log_post(db, topic, style, post_text, quality_score,
             was_published, rejection_reason=None):
    """Insert a new PostQualityLog row. Returns the created row or None."""
    try:
        row = PostQualityLog(
            topic=topic,
            style=style,
            post_text=post_text,
            quality_score=quality_score,
            was_published=was_published,
            rejection_reason=rejection_reason,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    except Exception as e:
        logger.error(f"log_post failed: {e}")
        db.rollback()
        return None


def update_comment_engagement(db, comment_id, got_reply, reply_count):
    """Update a CommentQualityLog row with engagement data."""
    try:
        row = db.query(CommentQualityLog).filter_by(id=comment_id).first()
        if row:
            if got_reply:
                row.got_reply = True
            row.reply_count = reply_count
            db.commit()
    except Exception as e:
        logger.error(f"update_comment_engagement failed: {e}")
        db.rollback()


def get_comment_quality_stats(db) -> dict:
    """Return aggregate comment quality statistics."""
    try:
        total = db.query(CommentQualityLog).count()
        if total == 0:
            return {
                "total_comments": 0,
                "avg_quality_score": 0.0,
                "high_quality_count": 0,
                "got_reply_count": 0,
                "reply_rate": 0.0,
                "top_angles": {"insight": 0, "contrarian": 0, "question": 0},
            }

        avg_score = db.query(func.avg(CommentQualityLog.quality_score)).scalar() or 0.0
        high_quality = db.query(CommentQualityLog).filter(
            CommentQualityLog.quality_score >= 8
        ).count()
        got_reply = db.query(CommentQualityLog).filter(
            CommentQualityLog.got_reply == True
        ).count()

        # Angle breakdown
        angle_rows = (
            db.query(CommentQualityLog.angle, func.count(CommentQualityLog.id))
            .group_by(CommentQualityLog.angle)
            .all()
        )
        top_angles = {"insight": 0, "contrarian": 0, "question": 0}
        for angle, count in angle_rows:
            if angle in top_angles:
                top_angles[angle] = count

        return {
            "total_comments": total,
            "avg_quality_score": round(float(avg_score), 2),
            "high_quality_count": high_quality,
            "got_reply_count": got_reply,
            "reply_rate": round(got_reply / total, 3) if total > 0 else 0.0,
            "top_angles": top_angles,
        }
    except Exception as e:
        logger.error(f"get_comment_quality_stats failed: {e}")
        return {
            "total_comments": 0,
            "avg_quality_score": 0.0,
            "high_quality_count": 0,
            "got_reply_count": 0,
            "reply_rate": 0.0,
            "top_angles": {"insight": 0, "contrarian": 0, "question": 0},
        }


def get_post_quality_stats(db) -> dict:
    """Return aggregate post quality statistics."""
    try:
        total = db.query(PostQualityLog).count()
        if total == 0:
            return {
                "total_generated": 0,
                "approved_count": 0,
                "rejected_count": 0,
                "approval_rate": 0.0,
                "avg_quality_score": 0.0,
                "top_rejection_reasons": [],
            }

        approved = db.query(PostQualityLog).filter(
            PostQualityLog.was_published == True
        ).count()
        rejected = total - approved

        avg_score = db.query(func.avg(PostQualityLog.quality_score)).scalar() or 0.0

        # Top rejection reasons
        reason_rows = (
            db.query(PostQualityLog.rejection_reason, func.count(PostQualityLog.id))
            .filter(
                PostQualityLog.rejection_reason.isnot(None),
                PostQualityLog.rejection_reason != "",
            )
            .group_by(PostQualityLog.rejection_reason)
            .order_by(func.count(PostQualityLog.id).desc())
            .limit(3)
            .all()
        )
        top_reasons = [r[0] for r in reason_rows]

        return {
            "total_generated": total,
            "approved_count": approved,
            "rejected_count": rejected,
            "approval_rate": round(approved / total, 3) if total > 0 else 0.0,
            "avg_quality_score": round(float(avg_score), 2),
            "top_rejection_reasons": top_reasons,
        }
    except Exception as e:
        logger.error(f"get_post_quality_stats failed: {e}")
        return {
            "total_generated": 0,
            "approved_count": 0,
            "rejected_count": 0,
            "approval_rate": 0.0,
            "avg_quality_score": 0.0,
            "top_rejection_reasons": [],
        }
