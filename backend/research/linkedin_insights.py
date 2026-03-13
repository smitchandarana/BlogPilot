"""
LinkedIn insights — extracts trending topics from existing feed scan data.

No external API calls — purely DB queries against the posts table
populated by the feed scanner pipeline.
"""
from datetime import datetime, timezone, timedelta

from sqlalchemy import func

from backend.storage.models import Post, TopicPerformance
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def get_trending_from_feed(db, days: int = 7) -> list[dict]:
    """
    Identify trending topics from feed posts scanned in the last N days.

    Groups posts by topic_tag and calculates engagement velocity.

    Returns:
        List of dicts: {topic, post_count, avg_likes, avg_comments, engagement_velocity}
        sorted by engagement_velocity desc.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    results = (
        db.query(
            Post.topic_tag,
            func.count(Post.id).label("post_count"),
            func.avg(Post.like_count).label("avg_likes"),
            func.avg(Post.comment_count).label("avg_comments"),
        )
        .filter(
            Post.created_at >= cutoff,
            Post.topic_tag.isnot(None),
            Post.topic_tag != "",
        )
        .group_by(Post.topic_tag)
        .having(func.count(Post.id) >= 2)
        .all()
    )

    topics = []
    for row in results:
        avg_likes = float(row.avg_likes or 0)
        avg_comments = float(row.avg_comments or 0)
        velocity = avg_likes + (avg_comments * 3)  # comments weighted higher

        topics.append({
            "topic": row.topic_tag,
            "post_count": row.post_count,
            "avg_likes": round(avg_likes, 1),
            "avg_comments": round(avg_comments, 1),
            "engagement_velocity": round(velocity, 1),
            "source": "LINKEDIN",
        })

    topics.sort(key=lambda x: x["engagement_velocity"], reverse=True)
    logger.info(f"LinkedInInsights: {len(topics)} trending topics from feed data")
    return topics


def get_high_engagement_posts(db, min_score: float = 7.0, days: int = 7) -> list[dict]:
    """
    Get recent high-scoring posts as context for content generation.

    Returns:
        List of dicts: {author, text_snippet, score, likes, comments, topic}
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    posts = (
        db.query(Post)
        .filter(
            Post.created_at >= cutoff,
            Post.relevance_score >= min_score,
            Post.text.isnot(None),
        )
        .order_by(Post.relevance_score.desc())
        .limit(20)
        .all()
    )

    return [
        {
            "author": p.author_name or "Unknown",
            "text_snippet": (p.text or "")[:300],
            "score": p.relevance_score,
            "likes": p.like_count or 0,
            "comments": p.comment_count or 0,
            "topic": p.topic_tag,
            "source": "LINKEDIN",
        }
        for p in posts
    ]


def get_topic_engagement_history(topic: str, db) -> dict:
    """
    Get historical engagement data for a topic from TopicPerformance table.

    Returns:
        Dict with engagement stats or empty dict if no data.
    """
    perf = (
        db.query(TopicPerformance)
        .filter(TopicPerformance.topic == topic)
        .first()
    )

    if not perf:
        return {}

    return {
        "posts_seen": perf.posts_seen,
        "posts_engaged": perf.posts_engaged,
        "engagement_rate": round(perf.engagement_rate, 3),
        "avg_score": round(perf.avg_score, 1),
        "comments_generated": perf.comments_generated,
        "likes_given": perf.likes_given,
        "is_active": perf.is_active,
    }
