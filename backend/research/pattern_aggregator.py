"""
Pattern Aggregator — computes recurring patterns from content_insights.

Aggregates ContentInsight rows into ContentPattern rows using SQL GROUP BY.
No vector search needed — categorical fields are sufficient at local scale.

Usage:
    agg = PatternAggregator()
    agg.aggregate_patterns(db)  # rebuilds content_patterns table
    pain_points = agg.get_trending_pain_points(db)
"""
from datetime import datetime, timezone

from backend.utils.logger import get_logger

logger = get_logger(__name__)


_STOP_WORDS = {
    'the', 'a', 'an', 'and', 'or', 'of', 'in', 'to', 'for', 'with', 'on', 'at',
    'is', 'are', 'was', 'were', 'be', 'been', 'not', 'no', 'by', 'as', 'it',
    'this', 'that', 'from', 'into', 'their', 'about', 'how', 'when', 'what',
}


def _keyword_set(text: str) -> set:
    """Extract meaningful keyword set from text for overlap scoring."""
    if not text:
        return set()
    return {
        w.lower().strip('.,;:()"\'')
        for w in text.split()
        if len(w) > 3 and w.lower().strip('.,;:()"\'') not in _STOP_WORDS
    }


def _relevance_score(query_topic: str, query_subtopic: str, insight) -> int:
    """Score how relevant a ContentInsight is to the query. Higher = more relevant."""
    query_words = _keyword_set(query_topic) | _keyword_set(query_subtopic)
    if not query_words:
        return 0
    insight_words = (
        _keyword_set(getattr(insight, 'topic', '') or '')
        | _keyword_set(getattr(insight, 'subtopic', '') or '')
        | _keyword_set(getattr(insight, 'pain_point', '') or '')
        | _keyword_set(getattr(insight, 'key_insight', '') or '')
    )
    return len(query_words & insight_words)


class PatternAggregator:
    """Aggregates content insights into recurring patterns."""

    # ── Main aggregation ──────────────────────────────────────────────────

    def aggregate_patterns(self, db) -> dict:
        """
        Rebuild content_patterns from content_insights using GROUP BY queries.

        Clears existing patterns first, then inserts fresh aggregations.
        Returns summary dict with counts per pattern type.
        """
        from backend.storage.models import ContentInsight, ContentPattern

        try:
            # Clear existing patterns
            db.query(ContentPattern).delete()
            db.commit()
        except Exception as e:
            logger.error(f"PatternAggregator: failed to clear patterns — {e}")
            db.rollback()
            return {"error": str(e)}

        counts = {}

        # 1. PAIN_POINT patterns — group by pain_point value
        counts["PAIN_POINT"] = self._aggregate_pain_points(db)

        # 2. HOOK patterns — group by hook_type
        counts["HOOK"] = self._aggregate_hooks(db)

        # 3. AUDIENCE patterns — group by audience_segment
        counts["AUDIENCE"] = self._aggregate_audiences(db)

        # 4. TOPIC_TREND patterns — group by subtopic
        counts["TOPIC_TREND"] = self._aggregate_topic_trends(db)

        total = sum(counts.values())
        logger.info(
            f"PatternAggregator: aggregated {total} patterns "
            f"(pain_points={counts['PAIN_POINT']}, hooks={counts['HOOK']}, "
            f"audiences={counts['AUDIENCE']}, trends={counts['TOPIC_TREND']})"
        )
        return counts

    # ── Query helpers ─────────────────────────────────────────────────────

    def get_patterns_for_topic(self, topic: str, db, limit: int = 10) -> list[dict]:
        """Return patterns relevant to a topic via LIKE match on domain/pattern_value."""
        from backend.storage.models import ContentPattern

        try:
            rows = (
                db.query(ContentPattern)
                .filter(ContentPattern.pattern_value.ilike(f"%{topic}%"))
                .order_by(
                    ContentPattern.frequency.desc(),
                    ContentPattern.avg_engagement.desc(),
                )
                .limit(limit)
                .all()
            )
            return [self._serialize(r) for r in rows]
        except Exception as e:
            logger.warning(f"PatternAggregator.get_patterns_for_topic: {e}")
            return []

    def get_trending_pain_points(self, db, limit: int = 5) -> list[dict]:
        """Top pain points by frequency × avg_engagement."""
        from backend.storage.models import ContentPattern

        try:
            rows = (
                db.query(ContentPattern)
                .filter(ContentPattern.pattern_type == "PAIN_POINT")
                .order_by(
                    ContentPattern.frequency.desc(),
                    ContentPattern.avg_engagement.desc(),
                )
                .limit(limit)
                .all()
            )
            return [self._serialize(r) for r in rows]
        except Exception as e:
            logger.warning(f"PatternAggregator.get_trending_pain_points: {e}")
            return []

    def get_effective_hooks(self, db, limit: int = 6) -> list[dict]:
        """Hook types ranked by avg source engagement."""
        from backend.storage.models import ContentPattern

        try:
            rows = (
                db.query(ContentPattern)
                .filter(ContentPattern.pattern_type == "HOOK")
                .order_by(ContentPattern.avg_engagement.desc())
                .limit(limit)
                .all()
            )
            return [self._serialize(r) for r in rows]
        except Exception as e:
            logger.warning(f"PatternAggregator.get_effective_hooks: {e}")
            return []

    def get_audience_segments(self, db, limit: int = 8) -> list[dict]:
        """Top audience segments by frequency."""
        from backend.storage.models import ContentPattern

        try:
            rows = (
                db.query(ContentPattern)
                .filter(ContentPattern.pattern_type == "AUDIENCE")
                .order_by(ContentPattern.frequency.desc())
                .limit(limit)
                .all()
            )
            return [self._serialize(r) for r in rows]
        except Exception as e:
            logger.warning(f"PatternAggregator.get_audience_segments: {e}")
            return []

    def get_trending_topics(self, db, limit: int = 10) -> list[dict]:
        """Topic trends ranked by recency + frequency."""
        from backend.storage.models import ContentPattern

        try:
            rows = (
                db.query(ContentPattern)
                .filter(ContentPattern.pattern_type == "TOPIC_TREND")
                .order_by(
                    ContentPattern.last_seen_at.desc(),
                    ContentPattern.frequency.desc(),
                )
                .limit(limit)
                .all()
            )
            return [self._serialize(r) for r in rows]
        except Exception as e:
            logger.warning(f"PatternAggregator.get_trending_topics: {e}")
            return []

    def get_evidence_block(self, topic: str, db, limit: int = 5, subtopic: str = "") -> str:
        """
        Format top insights related to a topic as an evidence text block
        for injection into the structured_post prompt.

        Uses keyword overlap scoring to prevent contamination from unrelated insights.
        Only includes insights with at least 1 shared keyword with topic/subtopic.
        """
        from backend.storage.models import ContentInsight

        query_topic = topic or ""
        query_subtopic = subtopic or ""

        try:
            # Wider fetch, then re-rank by keyword relevance
            candidates = (
                db.query(ContentInsight)
                .filter(
                    ContentInsight.topic.ilike(f"%{topic}%")
                    | ContentInsight.subtopic.ilike(f"%{topic}%")
                    | ContentInsight.subtopic.ilike(f"%{query_subtopic}%")
                )
                .filter(ContentInsight.specificity_score >= 4.0)
                .order_by(
                    ContentInsight.specificity_score.desc(),
                    ContentInsight.source_engagement.desc(),
                )
                .limit(limit * 4)  # fetch more, then filter by relevance
                .all()
            )
        except Exception as e:
            logger.warning(f"PatternAggregator.get_evidence_block: {e}")
            return ""

        if not candidates:
            return ""

        # Score relevance and filter out weakly related insights
        scored = [
            (r, _relevance_score(query_topic, query_subtopic, r))
            for r in candidates
        ]
        scored.sort(key=lambda x: (-x[1], -x[0].specificity_score, -x[0].source_engagement))

        # Only include insights with keyword overlap >= 1
        relevant = [(r, score) for r, score in scored if score >= 1]
        if not relevant:
            # Fall back to top candidates if nothing overlaps (broad topic like "Power BI")
            relevant = scored[:limit]

        lines = []
        for i, (r, _) in enumerate(relevant[:limit], 1):
            parts = []
            if r.key_insight:
                parts.append(f"Signal: {r.key_insight}")
            if r.pain_point and r.pain_point.lower() not in ("none", "not specified", ""):
                parts.append(f"Pain: {r.pain_point}")
            if r.subtopic:
                parts.append(f"Context: {r.subtopic}")
            if parts:
                lines.append(f"{i}. " + " | ".join(parts))

        return "\n".join(lines)

    def get_for_generation(self, topic: str, db) -> dict:
        """
        Return a curated set of patterns for the UI intelligence panel.
        Called by GET /intelligence/patterns/for-generation.
        """
        from backend.storage.models import ContentInsight

        # Get top insights for the topic
        try:
            recent_insights = (
                db.query(ContentInsight)
                .filter(
                    ContentInsight.topic.ilike(f"%{topic}%")
                    | ContentInsight.subtopic.ilike(f"%{topic}%")
                )
                .order_by(ContentInsight.specificity_score.desc())
                .limit(8)
                .all()
            )
            insights_list = [
                {
                    "id": r.id,
                    "subtopic": r.subtopic,
                    "pain_point": r.pain_point,
                    "hook_type": r.hook_type,
                    "key_insight": r.key_insight,
                    "audience_segment": r.audience_segment,
                    "specificity_score": r.specificity_score,
                    "source_type": r.source_type,
                }
                for r in recent_insights
            ]
        except Exception:
            insights_list = []

        return {
            "pain_points": self.get_trending_pain_points(db, limit=5),
            "hooks": self.get_effective_hooks(db, limit=6),
            "audiences": self.get_audience_segments(db, limit=5),
            "topic_trends": self.get_trending_topics(db, limit=5),
            "recent_insights": insights_list,
            "evidence_block": self.get_evidence_block(topic, db, limit=5),
        }

    # ── Aggregation helpers ───────────────────────────────────────────────

    def _aggregate_pain_points(self, db) -> int:
        """Group insights by pain_point, store as PAIN_POINT patterns."""
        from sqlalchemy import func
        from backend.storage.models import ContentInsight, ContentPattern

        try:
            rows = (
                db.query(
                    ContentInsight.pain_point,
                    func.count(ContentInsight.id).label("freq"),
                    func.avg(ContentInsight.source_engagement).label("avg_eng"),
                    func.group_concat(ContentInsight.id).label("ids"),
                    ContentInsight.topic,
                )
                .filter(
                    ContentInsight.pain_point.isnot(None),
                    ContentInsight.pain_point != "",
                    ContentInsight.pain_point != "none",
                    ContentInsight.pain_point != "None",
                )
                .group_by(ContentInsight.pain_point)
                .order_by(func.count(ContentInsight.id).desc())
                .limit(20)
                .all()
            )
        except Exception as e:
            logger.warning(f"PatternAggregator._aggregate_pain_points: {e}")
            return 0

        now = datetime.now(timezone.utc)
        count = 0
        for row in rows:
            try:
                ids = [int(x) for x in (row.ids or "").split(",") if x.strip().isdigit()][:3]
                pattern = ContentPattern(
                    pattern_type="PAIN_POINT",
                    pattern_value=row.pain_point[:512],
                    frequency=int(row.freq),
                    avg_engagement=float(row.avg_eng or 0),
                    example_insight_ids=ids,
                    domain=row.topic or "",
                    first_seen_at=now,
                    last_seen_at=now,
                )
                db.add(pattern)
                count += 1
            except Exception:
                pass

        try:
            db.commit()
        except Exception as e:
            logger.warning(f"PatternAggregator: pain_point commit failed — {e}")
            db.rollback()
        return count

    def _aggregate_hooks(self, db) -> int:
        """Group insights by hook_type, store as HOOK patterns."""
        from sqlalchemy import func
        from backend.storage.models import ContentInsight, ContentPattern

        try:
            rows = (
                db.query(
                    ContentInsight.hook_type,
                    func.count(ContentInsight.id).label("freq"),
                    func.avg(ContentInsight.source_engagement).label("avg_eng"),
                    func.group_concat(ContentInsight.id).label("ids"),
                )
                .filter(
                    ContentInsight.hook_type.isnot(None),
                    ContentInsight.hook_type != "",
                )
                .group_by(ContentInsight.hook_type)
                .order_by(func.avg(ContentInsight.source_engagement).desc())
                .all()
            )
        except Exception as e:
            logger.warning(f"PatternAggregator._aggregate_hooks: {e}")
            return 0

        now = datetime.now(timezone.utc)
        count = 0
        for row in rows:
            try:
                ids = [int(x) for x in (row.ids or "").split(",") if x.strip().isdigit()][:3]
                pattern = ContentPattern(
                    pattern_type="HOOK",
                    pattern_value=row.hook_type,
                    frequency=int(row.freq),
                    avg_engagement=float(row.avg_eng or 0),
                    example_insight_ids=ids,
                    first_seen_at=now,
                    last_seen_at=now,
                )
                db.add(pattern)
                count += 1
            except Exception:
                pass

        try:
            db.commit()
        except Exception as e:
            logger.warning(f"PatternAggregator: hook commit failed — {e}")
            db.rollback()
        return count

    def _aggregate_audiences(self, db) -> int:
        """Group insights by audience_segment, store as AUDIENCE patterns."""
        from sqlalchemy import func
        from backend.storage.models import ContentInsight, ContentPattern

        try:
            rows = (
                db.query(
                    ContentInsight.audience_segment,
                    func.count(ContentInsight.id).label("freq"),
                    func.avg(ContentInsight.source_engagement).label("avg_eng"),
                    func.group_concat(ContentInsight.id).label("ids"),
                )
                .filter(
                    ContentInsight.audience_segment.isnot(None),
                    ContentInsight.audience_segment != "",
                )
                .group_by(ContentInsight.audience_segment)
                .order_by(func.count(ContentInsight.id).desc())
                .limit(20)
                .all()
            )
        except Exception as e:
            logger.warning(f"PatternAggregator._aggregate_audiences: {e}")
            return 0

        now = datetime.now(timezone.utc)
        count = 0
        for row in rows:
            try:
                ids = [int(x) for x in (row.ids or "").split(",") if x.strip().isdigit()][:3]
                pattern = ContentPattern(
                    pattern_type="AUDIENCE",
                    pattern_value=row.audience_segment[:512],
                    frequency=int(row.freq),
                    avg_engagement=float(row.avg_eng or 0),
                    example_insight_ids=ids,
                    first_seen_at=now,
                    last_seen_at=now,
                )
                db.add(pattern)
                count += 1
            except Exception:
                pass

        try:
            db.commit()
        except Exception as e:
            logger.warning(f"PatternAggregator: audience commit failed — {e}")
            db.rollback()
        return count

    def _aggregate_topic_trends(self, db) -> int:
        """Group insights by subtopic, store as TOPIC_TREND patterns."""
        from sqlalchemy import func
        from backend.storage.models import ContentInsight, ContentPattern

        try:
            rows = (
                db.query(
                    ContentInsight.subtopic,
                    ContentInsight.topic,
                    func.count(ContentInsight.id).label("freq"),
                    func.avg(ContentInsight.source_engagement).label("avg_eng"),
                    func.avg(ContentInsight.specificity_score).label("avg_score"),
                    func.group_concat(ContentInsight.id).label("ids"),
                    func.max(ContentInsight.created_at).label("latest"),
                )
                .filter(
                    ContentInsight.subtopic.isnot(None),
                    ContentInsight.subtopic != "",
                )
                .group_by(ContentInsight.subtopic)
                .order_by(func.count(ContentInsight.id).desc())
                .limit(30)
                .all()
            )
        except Exception as e:
            logger.warning(f"PatternAggregator._aggregate_topic_trends: {e}")
            return 0

        now = datetime.now(timezone.utc)
        count = 0
        for row in rows:
            try:
                ids = [int(x) for x in (row.ids or "").split(",") if x.strip().isdigit()][:3]
                last_seen = row.latest if isinstance(row.latest, datetime) else now
                pattern = ContentPattern(
                    pattern_type="TOPIC_TREND",
                    pattern_value=row.subtopic[:512],
                    frequency=int(row.freq),
                    avg_engagement=float(row.avg_eng or 0),
                    example_insight_ids=ids,
                    domain=row.topic or "",
                    first_seen_at=now,
                    last_seen_at=last_seen,
                )
                db.add(pattern)
                count += 1
            except Exception:
                pass

        try:
            db.commit()
        except Exception as e:
            logger.warning(f"PatternAggregator: topic_trend commit failed — {e}")
            db.rollback()
        return count

    @staticmethod
    def _serialize(pattern) -> dict:
        return {
            "id": pattern.id,
            "pattern_type": pattern.pattern_type,
            "pattern_value": pattern.pattern_value,
            "frequency": pattern.frequency,
            "avg_engagement": pattern.avg_engagement,
            "example_insight_ids": pattern.example_insight_ids or [],
            "domain": pattern.domain,
            "last_seen_at": pattern.last_seen_at.isoformat() if pattern.last_seen_at else None,
        }
