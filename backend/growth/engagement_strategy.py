"""
Engagement Strategy — Sprint 7.

Decides what action to take on a scored post given the current
budget, mode setting, and relevance score.

Replaces the stub _decide_action() in pipeline.py.
"""
from backend.utils.config_loader import get as cfg_get
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Action constants
LIKE = "LIKE"
COMMENT = "COMMENT"
LIKE_AND_COMMENT = "LIKE_AND_COMMENT"
SKIP = "SKIP"


def decide(score: float, budget_remaining: dict, mode: str = "smart") -> str:
    """
    Decide the action to take for a post.

    Args:
        score:            Relevance score (0–10) from the AI classifier.
        budget_remaining: Dict of {action_type: bool} — True means budget OK.
                          Expected keys: "likes", "comments".
        mode:             Engagement mode from config:
                          like_only | comment_only | like_and_comment | smart

    Returns:
        One of: LIKE | COMMENT | LIKE_AND_COMMENT | SKIP
    """
    can_like: bool = bool(budget_remaining.get("likes", False))
    can_comment: bool = bool(budget_remaining.get("comments", False))

    min_score: float = float(cfg_get("feed_engagement.min_relevance_score", 6))

    if score < min_score:
        logger.debug(f"Strategy: SKIP — score {score:.1f} below threshold {min_score}")
        return SKIP

    if mode == "like_only":
        if can_like:
            return LIKE
        logger.debug("Strategy: SKIP — like budget exhausted")
        return SKIP

    if mode == "comment_only":
        if can_comment:
            return COMMENT
        logger.debug("Strategy: SKIP — comment budget exhausted")
        return SKIP

    if mode == "like_and_comment":
        if can_like and can_comment:
            return LIKE_AND_COMMENT
        if can_like:
            # Comment budget gone — downgrade to like
            logger.debug("Strategy: LIKE — comment budget exhausted, downgrading")
            return LIKE
        logger.debug("Strategy: SKIP — like budget exhausted")
        return SKIP

    # smart (default)
    if score >= 8:
        if can_like and can_comment:
            return LIKE_AND_COMMENT
        if can_like:
            logger.debug("Strategy: LIKE — high score but comment budget gone")
            return LIKE
        return SKIP

    if score >= 6:
        if can_like:
            return LIKE
        return SKIP

    return SKIP


def get_budget_flags(db) -> dict:
    """
    Helper: build the budget_remaining dict expected by decide().
    Checks likes and comments budget against the DB tracker.
    """
    from backend.storage import budget_tracker
    return {
        "likes": budget_tracker.check("likes", db),
        "comments": budget_tracker.check("comments", db),
    }
