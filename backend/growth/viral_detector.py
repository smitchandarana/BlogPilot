"""
Viral Detector — Sprint 7.

Calculates engagement velocity for a post and determines whether it
qualifies as "viral" based on configured thresholds.

Used by the pipeline (Step 5) to prioritise high-velocity posts.
"""
from datetime import datetime, timezone
from typing import Optional

from backend.core.task_queue import Priority
from backend.utils.config_loader import get as cfg_get
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def is_viral(
    like_count: int,
    comment_count: int,
    post_timestamp: Optional[datetime] = None,
) -> bool:
    """
    Return True if the post is gaining engagement fast enough to be
    considered viral.

    If post_timestamp is None (unknown), falls back to raw count thresholds.
    """
    like_threshold: int = int(cfg_get("viral_detection.likes_per_hour_threshold", 50))
    comment_threshold: int = int(cfg_get("viral_detection.comments_per_hour_threshold", 10))

    if post_timestamp is None:
        # No timestamp — use raw counts as a rough proxy
        return like_count >= like_threshold or comment_count >= comment_threshold

    # Normalise timestamp to UTC-aware
    if post_timestamp.tzinfo is None:
        post_timestamp = post_timestamp.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    hours_elapsed = max((now - post_timestamp).total_seconds() / 3600, 0.1)

    likes_per_hour = like_count / hours_elapsed
    comments_per_hour = comment_count / hours_elapsed

    viral = likes_per_hour >= like_threshold or comments_per_hour >= comment_threshold

    if viral:
        logger.debug(
            f"ViralDetector: viral post detected — "
            f"{likes_per_hour:.1f} likes/h, {comments_per_hour:.1f} comments/h"
        )

    return viral


def get_priority(viral: bool) -> Priority:
    """
    Map viral flag → task queue priority.

    Reads priority_boost from config; defaults to HIGH for viral posts.
    """
    if not viral:
        return Priority.NORMAL

    boost = str(cfg_get("viral_detection.priority_boost", "high")).lower()
    return Priority.HIGH if boost == "high" else Priority.NORMAL
