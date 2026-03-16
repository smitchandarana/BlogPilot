"""
Topic Rotator — Sprint 9.

Auto-rotation engine for topics. Tracks engagement performance per topic,
demotes underperformers, and promotes fresh topics on a 24-hour cycle.
"""
import os
from datetime import datetime, timedelta

from backend.utils.logger import get_logger
from backend.utils.config_loader import get as cfg_get, load_config

logger = get_logger(__name__)

_CONFIG_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "config", "settings.yaml")
)

# ── Topic → Hashtag mapping (covers TOPICS.md primary categories) ─────────

TOPIC_HASHTAG_MAP = {
    "Business Intelligence": ["#businessintelligence", "#bi", "#dataanalytics", "#dashboard", "#reporting"],
    "Data Analytics": ["#dataanalytics", "#analytics", "#datadriven", "#datascience", "#datainsights"],
    "Reporting Solutions": ["#reporting", "#businessreporting", "#datareporting", "#kpi", "#dashboard"],
    "Dashboard Design": ["#dashboarddesign", "#datavisualization", "#dataviz", "#uidesign", "#dashboard"],
    "Data Visualization": ["#dataviz", "#datavisualization", "#datastorytelling", "#visualanalytics", "#datadesign"],
    "Business Reporting": ["#businessreporting", "#reporting", "#kpis", "#businessanalytics", "#performancemetrics"],
    "KPI Tracking": ["#kpi", "#kpis", "#performancemetrics", "#businessperformance", "#metricsmatter"],
    "Financial Reporting": ["#financialreporting", "#financeanalytics", "#fpanda", "#financialdashboard", "#financialinsights"],
    "Sales Analytics": ["#salesanalytics", "#revenueanalytics", "#salesperformance", "#salesdashboard", "#pipelineanalytics"],
    "Operations Analytics": ["#operationsmanagement", "#operationalanalytics", "#processoptimization", "#efficiency", "#operationalexcellence"],
    "Power BI": ["#powerbi", "#microsoftfabric", "#dataanalytics", "#businessintelligence", "#dashboard"],
    "Tableau": ["#tableau", "#dataviz", "#datavisualization", "#analytics", "#dashboard"],
    "Data Strategy": ["#datastrategy", "#datadriven", "#dataleadership", "#datamaturity", "#dataculture"],
    "Digital Transformation": ["#digitaltransformation", "#digitalstrategy", "#automation", "#hyperautomation", "#digitalinnovation"],
    "Data-Driven Decision Making": ["#datadrivendecisions", "#dataculture", "#decisionintelligence", "#analyticsculture", "#datafirst"],
    "Excel Automation": ["#excelauto", "#excelautomation", "#spreadsheets", "#productivity", "#dataanalytics"],
    "Business Performance": ["#businessperformance", "#performanceanalytics", "#kpis", "#businessgrowth", "#operationalexcellence"],
    "Revenue Analytics": ["#revenueanalytics", "#revenuegrowth", "#revenueoperations", "#salesanalytics", "#pipelineanalytics"],
    "Customer Analytics": ["#customeranalytics", "#customerinsights", "#customersuccess", "#analyticsdriven", "#datapowered"],
    "Supply Chain Analytics": ["#supplychainanalytics", "#logistics", "#operationsmanagement", "#supplychain", "#efficiency"],
    "HR Analytics": ["#hranalytics", "#peopleanalytics", "#workforceanalytics", "#hrtechnology", "#talentanalytics"],
}

_DEFAULT_HASHTAGS = ["#dataanalytics", "#businessintelligence", "#reporting"]


class TopicRotator:
    """Manages topic performance tracking and auto-rotation cycles."""

    def __init__(self):
        self._last_cycle_report = None

    # ── Read ──────────────────────────────────────────────────────────────

    def get_all_topics(self, db) -> dict:
        """Return active, paused, and available topics with performance stats."""
        from backend.storage.models import TopicPerformance

        rows = db.query(TopicPerformance).all()
        db_topic_names = {r.topic for r in rows}

        yaml_topics = cfg_get("topics", []) or []

        active = [
            {
                "topic": r.topic,
                "engagement_rate": r.engagement_rate,
                "avg_score": r.avg_score,
                "posts_engaged": r.posts_engaged,
                "posts_seen": r.posts_seen,
            }
            for r in rows
            if r.is_active and not r.is_paused
        ]

        paused = [
            {
                "topic": r.topic,
                "pause_reason": r.pause_reason or "",
                "last_used": r.last_used.isoformat() if r.last_used else None,
            }
            for r in rows
            if r.is_paused
        ]

        available = [t for t in yaml_topics if t not in db_topic_names]

        return {"active": active, "paused": paused, "available": available}

    # ── Activate / Deactivate ─────────────────────────────────────────────

    def activate_topic(self, topic: str, db) -> bool:
        """Activate a topic — insert if new, un-pause if paused."""
        from backend.storage.models import TopicPerformance

        try:
            row = db.query(TopicPerformance).filter_by(topic=topic).first()
            if row is None:
                row = TopicPerformance(
                    topic=topic,
                    is_active=True,
                    is_paused=False,
                )
                db.add(row)
            else:
                row.is_active = True
                row.is_paused = False
                row.pause_reason = None
                row.last_rotated = datetime.utcnow()
            db.commit()

            # Sync to settings.yaml
            self._add_topic_to_yaml(topic)
            logger.info(f"TopicRotator: activated '{topic}'")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"TopicRotator: activate_topic failed — {e}")
            return False

    def deactivate_topic(self, topic: str, db) -> bool:
        """Pause a topic manually. Does NOT remove from settings.yaml."""
        from backend.storage.models import TopicPerformance

        try:
            row = db.query(TopicPerformance).filter_by(topic=topic).first()
            if row is None:
                return False
            row.is_active = False
            row.is_paused = True
            row.pause_reason = "manual"
            db.commit()
            logger.info(f"TopicRotator: deactivated '{topic}' (manual)")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"TopicRotator: deactivate_topic failed — {e}")
            return False

    # ── Engagement Recording ──────────────────────────────────────────────

    def record_engagement(self, topic: str, score: float, action_taken: str, db):
        """Upsert topic performance stats after a pipeline action."""
        from backend.storage.models import TopicPerformance

        try:
            row = db.query(TopicPerformance).filter_by(topic=topic).first()
            if row is None:
                row = TopicPerformance(topic=topic, is_active=True, is_paused=False)
                db.add(row)
                db.flush()

            row.posts_seen += 1
            row.last_used = datetime.utcnow()

            if action_taken != "SKIP":
                row.posts_engaged += 1
                if action_taken == "COMMENT" or action_taken == "LIKE_AND_COMMENT":
                    row.comments_generated += 1
                if action_taken == "LIKE" or action_taken == "LIKE_AND_COMMENT":
                    row.likes_given += 1

            # Rolling average score
            if row.posts_seen > 1:
                row.avg_score = ((row.avg_score * (row.posts_seen - 1)) + score) / row.posts_seen
            else:
                row.avg_score = score

            # Engagement rate
            row.engagement_rate = row.posts_engaged / row.posts_seen if row.posts_seen > 0 else 0.0

            db.commit()
        except Exception as e:
            db.rollback()
            logger.warning(f"TopicRotator: record_engagement failed — {e}")

    # ── Iteration Cycle ───────────────────────────────────────────────────

    def run_iteration_cycle(self, db) -> dict:
        """
        Core auto-rotation logic. Called by scheduler every 24h or manually.

        Step 1: Score active topics
        Step 2: Demote underperformers
        Step 3: Promote from available pool
        Step 4: Hashtag sync
        Step 5: Return cycle report
        """
        from backend.storage.models import TopicPerformance

        now = datetime.utcnow()
        min_posts = int(cfg_get("topic_rotation.min_posts_before_scoring", 10))
        low_threshold = float(cfg_get("topic_rotation.low_engagement_threshold", 0.15))
        target_active = int(cfg_get("topic_rotation.target_active_count", 8))
        max_new = int(cfg_get("topic_rotation.max_new_topics_per_cycle", 2))
        min_active = int(cfg_get("topic_rotation.min_active_topics", 5))
        retry_days = int(cfg_get("topic_rotation.retry_paused_after_days", 7))

        topics_paused = []
        topics_activated = []

        all_rows = db.query(TopicPerformance).all()

        # ── Step 1: Score active topics ─────────────────────────────────
        active_rows = [r for r in all_rows if r.is_active and not r.is_paused]
        scored = []
        for r in active_rows:
            if r.posts_seen >= min_posts:
                perf = (
                    (r.engagement_rate * 0.5)
                    + (r.avg_score / 10.0 * 0.3)
                    + (min(r.posts_engaged, 50) / 50.0 * 0.2)
                )
                scored.append((r, perf))

        # ── Step 2: Demote underperformers ──────────────────────────────
        current_active_count = len(active_rows)
        for r, perf in scored:
            if perf < low_threshold and r.posts_seen >= min_posts:
                # Never drop below min_active_topics
                if current_active_count <= min_active:
                    break
                # Never touch manual pauses
                if r.pause_reason == "manual":
                    continue

                r.is_paused = True
                r.pause_reason = f"low_engagement: {r.engagement_rate:.0%} rate"
                r.last_rotated = now
                topics_paused.append(r.topic)
                current_active_count -= 1
                logger.info(f"TopicRotator: paused '{r.topic}' — {r.pause_reason}")

        # ── Step 3: Promote from available pool ─────────────────────────
        active_after_demote = current_active_count
        slots_to_fill = target_active - active_after_demote
        slots_to_fill = max(0, min(slots_to_fill, max_new))

        if slots_to_fill > 0:
            yaml_topics = cfg_get("topics", []) or []
            db_topic_names = {r.topic for r in all_rows}

            # Candidates: topics not in DB at all
            never_tried = [t for t in yaml_topics if t not in db_topic_names]

            # Candidates: paused with low_engagement reason and old enough
            retry_cutoff = now - timedelta(days=retry_days)
            retryable = [
                r for r in all_rows
                if r.is_paused
                and r.pause_reason is not None
                and r.pause_reason.startswith("low_engagement")
                and r.last_rotated is not None
                and r.last_rotated < retry_cutoff
            ]

            promoted = 0
            # Try never-tried first
            for t in never_tried:
                if promoted >= slots_to_fill:
                    break
                self.activate_topic(t, db)
                topics_activated.append(t)
                promoted += 1

            # Then retry old paused topics
            for r in retryable:
                if promoted >= slots_to_fill:
                    break
                self.activate_topic(r.topic, db)
                topics_activated.append(r.topic)
                promoted += 1

        # ── Step 4: Hashtag sync ────────────────────────────────────────
        if topics_activated:
            self._sync_hashtags_for_topics(topics_activated)

        # ── Step 5: Build cycle report ──────────────────────────────────
        # Re-query for accurate counts
        final_active = (
            db.query(TopicPerformance)
            .filter_by(is_active=True, is_paused=False)
            .all()
        )

        top_performer = None
        low_performer = None
        if final_active:
            best = max(final_active, key=lambda r: r.engagement_rate)
            worst = min(final_active, key=lambda r: r.engagement_rate)
            top_performer = {"topic": best.topic, "engagement_rate": best.engagement_rate}
            low_performer = {"topic": worst.topic, "engagement_rate": worst.engagement_rate}

        report = {
            "topics_paused": topics_paused,
            "topics_activated": topics_activated,
            "top_performer": top_performer,
            "low_performer": low_performer,
            "active_count": len(final_active),
            "cycle_timestamp": now.isoformat(),
        }

        self._last_cycle_report = report
        logger.info(
            f"TopicRotator: cycle complete — "
            f"activated={len(topics_activated)}, paused={len(topics_paused)}, "
            f"active={len(final_active)}"
        )
        return report

    @property
    def last_cycle_report(self):
        return self._last_cycle_report

    # ── Hashtag Suggestions ───────────────────────────────────────────────

    def get_hashtag_suggestions(self, topic: str) -> list:
        """Return top 5 relevant hashtags for the given topic."""
        return TOPIC_HASHTAG_MAP.get(topic, _DEFAULT_HASHTAGS)[:5]

    # ── Internal helpers ──────────────────────────────────────────────────

    def _add_topic_to_yaml(self, topic: str):
        """Append topic to settings.yaml topics list if not already present."""
        import yaml

        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            topics_list = data.get("topics", []) or []
            if topic not in topics_list:
                topics_list.append(topic)
                data["topics"] = topics_list
                with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
                    yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)
                load_config()
        except Exception as e:
            logger.warning(f"TopicRotator: failed to sync topic to yaml — {e}")

    def _sync_hashtags_for_topics(self, topics: list):
        """Append hashtag suggestions for newly activated topics to settings.yaml."""
        import yaml

        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            current_hashtags = data.get("hashtags", []) or []
            new_hashtags = set()
            for t in topics:
                for h in self.get_hashtag_suggestions(t):
                    if h not in current_hashtags:
                        new_hashtags.add(h)
            if new_hashtags:
                current_hashtags.extend(sorted(new_hashtags))
                data["hashtags"] = current_hashtags
                with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
                    yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)
                load_config()
        except Exception as e:
            logger.warning(f"TopicRotator: failed to sync hashtags — {e}")


# ── Module-level singleton ────────────────────────────────────────────────
topic_rotator = TopicRotator()
