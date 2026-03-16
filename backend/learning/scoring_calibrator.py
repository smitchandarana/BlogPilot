"""
Scoring calibrator — Phase C2.

Analyzes the correlation between relevance scores and actual engagement outcomes.
Groups posts by score bucket and calculates engagement/reply rates per bucket.
Returns recommendations for optimal scoring thresholds.
"""
from sqlalchemy import func, case
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ScoringCalibrator:
    """Analyze score vs outcome correlations to calibrate thresholds."""

    # Score buckets: label → (min, max) inclusive
    BUCKETS = [
        ("0-3", 0, 3),
        ("4-5", 4, 5),
        ("6-7", 6, 7),
        ("8-10", 8, 10),
    ]

    def analyze(self, db) -> dict:
        """
        Return score calibration data with per-bucket engagement rates.

        Returns:
            {
                "buckets": [
                    {"range": "0-3", "total": 10, "acted": 0, "rate": 0.0},
                    ...
                ],
                "comment_buckets": [
                    {"range": "0-3", "total": 0, "got_reply": 0, "reply_rate": 0.0},
                    ...
                ],
                "optimal_min_score": 6.0,
                "recommendation": "...",
                "total_posts": 100,
            }
        """
        from backend.storage.models import Post, CommentQualityLog

        try:
            # ── Post score buckets ──
            post_buckets = []
            total_posts = 0

            for label, lo, hi in self.BUCKETS:
                total = (
                    db.query(Post)
                    .filter(
                        Post.relevance_score >= lo,
                        Post.relevance_score <= hi,
                        Post.relevance_score.isnot(None),
                    )
                    .count()
                )
                acted = (
                    db.query(Post)
                    .filter(
                        Post.relevance_score >= lo,
                        Post.relevance_score <= hi,
                        Post.state == "ACTED",
                    )
                    .count()
                )
                rate = round(acted / total, 3) if total > 0 else 0.0
                post_buckets.append({
                    "range": label,
                    "total": total,
                    "acted": acted,
                    "rate": rate,
                })
                total_posts += total

            # ── Comment quality score buckets ──
            comment_buckets = []
            for label, lo, hi in self.BUCKETS:
                total = (
                    db.query(CommentQualityLog)
                    .filter(
                        CommentQualityLog.quality_score >= lo,
                        CommentQualityLog.quality_score <= hi,
                    )
                    .count()
                )
                got_reply = (
                    db.query(CommentQualityLog)
                    .filter(
                        CommentQualityLog.quality_score >= lo,
                        CommentQualityLog.quality_score <= hi,
                        CommentQualityLog.got_reply == True,
                    )
                    .count()
                )
                reply_rate = round(got_reply / total, 3) if total > 0 else 0.0
                comment_buckets.append({
                    "range": label,
                    "total": total,
                    "got_reply": got_reply,
                    "reply_rate": reply_rate,
                })

            # ── Recommendation ──
            optimal, recommendation = self._recommend(post_buckets, comment_buckets, total_posts)

            return {
                "buckets": post_buckets,
                "comment_buckets": comment_buckets,
                "optimal_min_score": optimal,
                "recommendation": recommendation,
                "total_posts": total_posts,
            }

        except Exception as e:
            logger.error(f"ScoringCalibrator: analysis failed: {e}")
            return {
                "buckets": [],
                "comment_buckets": [],
                "optimal_min_score": 6.0,
                "recommendation": "Insufficient data",
                "total_posts": 0,
            }

    def _recommend(self, post_buckets, comment_buckets, total_posts) -> tuple:
        """Generate optimal score recommendation based on bucket data."""
        if total_posts < 20:
            return 6.0, "Need at least 20 scored posts for calibration"

        # Find the lowest bucket with a meaningful engagement rate (>30%)
        optimal = 6.0
        for bucket in post_buckets:
            lo = int(bucket["range"].split("-")[0])
            if bucket["total"] >= 5 and bucket["rate"] >= 0.3:
                optimal = float(lo)
                break

        # Check if comment quality correlates with replies
        comment_note = ""
        for cb in comment_buckets:
            if cb["range"] == "8-10" and cb["total"] >= 5:
                if cb["reply_rate"] > 0.2:
                    comment_note = f" High-quality comments (8-10) get {cb['reply_rate']:.0%} reply rate."

        recommendation = f"Suggested minimum relevance score: {optimal:.0f}.{comment_note}"
        return optimal, recommendation


# Module-level singleton
scoring_calibrator = ScoringCalibrator()
