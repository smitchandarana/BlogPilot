"""
Content Preference Learner — Phase B of Content Intelligence.

Analyzes GenerationSession history to surface:
- Which hook types led to published posts
- Which audiences the user targets most
- Pain points that generated the highest-scoring posts
- Default form values for the structured generator

Called by GET /intelligence/preferences.
"""
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ContentPreferenceLearner:
    """Mines generation sessions for user preferences and patterns."""

    MIN_SESSIONS = 3  # don't infer preferences until we have enough data

    def get_preferences(self, db) -> dict:
        """
        Return a structured dict of learned preferences.
        Falls back to empty defaults if insufficient history.
        """
        from backend.storage.models import GenerationSession

        try:
            total = db.query(GenerationSession).count()
            published = (
                db.query(GenerationSession)
                .filter(GenerationSession.action == "published")
                .all()
            )
            all_sessions = db.query(GenerationSession).all()
            top_posts = (
                db.query(GenerationSession)
                .filter(
                    GenerationSession.action == "published",
                    GenerationSession.final_text.isnot(None),
                    GenerationSession.final_text != "",
                )
                .order_by(GenerationSession.quality_score.desc())
                .limit(3)
                .all()
            )
        except Exception as e:
            logger.warning(f"ContentPreferenceLearner: DB error — {e}")
            return self._empty()

        if total < self.MIN_SESSIONS:
            return {**self._empty(), "total_sessions": total, "has_data": False}

        return {
            "has_data": True,
            "total_sessions": total,
            "published_count": len(published),
            "best_hook_types": self._rank_hook_types(published, all_sessions),
            "preferred_audiences": self._top_values("audience", published, limit=5),
            "common_pain_points": self._top_values("pain_point", all_sessions, limit=5),
            "best_topics": self._top_values("topic", published, limit=8),
            "best_styles": self._rank_styles(published),
            "avg_edit_ratio": self._avg_edit_ratio(all_sessions),
            "default_hook": self._best_hook(published),
            "default_audience": self._most_common("audience", published),
            "default_style": self._most_common("style", published),
            "top_posts": [
                {
                    "topic": s.topic or "",
                    "hook_intent": s.hook_intent or "",
                    "style": s.style or "",
                    "tone": s.tone or "",
                    "preview": (s.final_text or "")[:300],
                }
                for s in top_posts
            ],
        }

    # ── Private helpers ───────────────────────────────────────────────────

    def _rank_hook_types(self, published: list, all_sessions: list) -> list[dict]:
        """Rank hook types by publish rate."""
        from collections import Counter

        all_hooks = Counter(s.hook_intent for s in all_sessions if s.hook_intent)
        pub_hooks = Counter(s.hook_intent for s in published if s.hook_intent)

        result = []
        for hook, total_count in all_hooks.most_common():
            pub_count = pub_hooks.get(hook, 0)
            result.append({
                "hook_type": hook,
                "total_used": total_count,
                "times_published": pub_count,
                "publish_rate": round(pub_count / total_count, 2) if total_count > 0 else 0.0,
            })
        result.sort(key=lambda x: (-x["publish_rate"], -x["total_used"]))
        return result

    def _top_values(self, field: str, sessions: list, limit: int = 5) -> list[str]:
        """Return most common non-empty values for a field."""
        from collections import Counter
        counts = Counter(
            getattr(s, field, "").strip()
            for s in sessions
            if getattr(s, field, "")
        )
        return [v for v, _ in counts.most_common(limit) if v]

    def _rank_styles(self, published: list) -> list[dict]:
        from collections import Counter
        counts = Counter(s.style for s in published if s.style)
        return [{"style": style, "count": count} for style, count in counts.most_common()]

    def _avg_edit_ratio(self, sessions: list) -> float:
        ratios = [s.edit_distance_ratio for s in sessions if s.edit_distance_ratio is not None]
        if not ratios:
            return 0.0
        return round(sum(ratios) / len(ratios), 3)

    def _best_hook(self, published: list) -> str:
        """Hook type that appears most in published sessions."""
        if not published:
            return "STORY"
        from collections import Counter
        counts = Counter(s.hook_intent for s in published if s.hook_intent)
        return counts.most_common(1)[0][0] if counts else "STORY"

    def _most_common(self, field: str, sessions: list) -> str:
        if not sessions:
            return ""
        from collections import Counter
        counts = Counter(getattr(s, field, "") for s in sessions if getattr(s, field, ""))
        return counts.most_common(1)[0][0] if counts else ""

    def _empty(self) -> dict:
        return {
            "has_data": False,
            "total_sessions": 0,
            "published_count": 0,
            "best_hook_types": [],
            "preferred_audiences": [],
            "common_pain_points": [],
            "best_topics": [],
            "best_styles": [],
            "avg_edit_ratio": 0.0,
            "default_hook": "STORY",
            "default_audience": "",
            "default_style": "Thought Leadership",
            "top_posts": [],
        }
