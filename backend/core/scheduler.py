import os
from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from backend.utils.config_loader import get as cfg_get
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_DB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
_SCHEDULER_DB = os.path.join(_DB_DIR, "scheduler.db")


class Scheduler:
    """APScheduler wrapper backed by SQLite for job persistence across restarts."""

    def __init__(self):
        os.makedirs(_DB_DIR, exist_ok=True)
        self._db_url = f"sqlite:///{os.path.abspath(_SCHEDULER_DB)}"
        self._scheduler = None
        self._started: bool = False

    def _create_scheduler(self):
        """Create a fresh BackgroundScheduler instance (APScheduler cannot restart after shutdown)."""
        jobstores = {"default": SQLAlchemyJobStore(url=self._db_url)}
        return BackgroundScheduler(
            jobstores=jobstores,
            job_defaults={"coalesce": True, "max_instances": 1},
        )

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def start(self):
        if not self._started:
            self._scheduler = self._create_scheduler()
            self._scheduler.start()
            self._started = True
            self._scheduler.remove_all_jobs()  # purge stale jobs from previous runs
            self._register_default_jobs()
            logger.info("Scheduler started")

    def stop(self):
        if self._started and self._scheduler is not None and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            self._started = False
            logger.info("Scheduler stopped")

    def pause(self):
        if self._started and self._scheduler is not None and self._scheduler.running:
            self._scheduler.pause()
            logger.info("Scheduler paused — jobs will not fire")

    def resume(self):
        if self._started and self._scheduler is not None and self._scheduler.running:
            self._scheduler.resume()
            logger.info("Scheduler resumed")

    # ── Job management ─────────────────────────────────────────────────────

    def add_job(
        self,
        fn: Callable,
        trigger,
        job_id: str,
        replace_existing: bool = True,
        **kwargs,
    ):
        if self._scheduler is None:
            logger.warning(f"Scheduler: cannot add job '{job_id}' — scheduler not running")
            return
        self._scheduler.add_job(
            fn,
            trigger,
            id=job_id,
            replace_existing=replace_existing,
            **kwargs,
        )
        logger.debug(f"Scheduler: job added — {job_id}")

    def remove_job(self, job_id: str):
        try:
            self._scheduler.remove_job(job_id)
            logger.debug(f"Scheduler: job removed — {job_id}")
        except Exception as exc:
            logger.warning(f"Scheduler: could not remove job '{job_id}': {exc}")

    def reschedule_feed_scan(self, interval_minutes: int):
        try:
            self._scheduler.reschedule_job(
                "feed_scan",
                trigger=IntervalTrigger(minutes=interval_minutes),
            )
            logger.info(f"Scheduler: feed_scan rescheduled — every {interval_minutes} min")
        except Exception as exc:
            logger.warning(f"Scheduler: reschedule failed: {exc}")

    # ── Default jobs ───────────────────────────────────────────────────────

    def _register_default_jobs(self):
        interval = int(cfg_get("schedule.feed_scan_interval_minutes", 20))
        feed_jitter = int(cfg_get("schedule.feed_scan_jitter_seconds", 300))

        self._scheduler.add_job(
            _job_feed_scan,
            IntervalTrigger(minutes=interval, jitter=feed_jitter),
            id="feed_scan",
            replace_existing=True,
        )
        self._scheduler.add_job(
            _job_hourly_reset,
            CronTrigger(minute=0),
            id="hourly_reset",
            replace_existing=True,
        )
        self._scheduler.add_job(
            _job_budget_reset,
            CronTrigger(hour=0, minute=1),
            id="budget_reset",
            replace_existing=True,
        )
        self._scheduler.add_job(
            _job_campaign_processing,
            IntervalTrigger(minutes=30, jitter=180),
            id="campaign_processing",
            replace_existing=True,
        )
        self._scheduler.add_job(
            _job_post_publishing,
            IntervalTrigger(minutes=1),
            id="post_publishing",
            replace_existing=True,
        )
        cycle_hours = int(cfg_get("topic_rotation.cycle_interval_hours", 24))
        if cfg_get("topic_rotation.enabled", True):
            self._scheduler.add_job(
                _job_topic_rotation,
                IntervalTrigger(hours=cycle_hours, jitter=1800),
                id="topic_rotation_cycle",
                replace_existing=True,
            )
        research_hours = int(cfg_get("research.scan_interval_hours", 6))
        if cfg_get("research.enabled", True):
            self._scheduler.add_job(
                _job_topic_research,
                IntervalTrigger(hours=research_hours, jitter=600),
                id="topic_research",
                replace_existing=True,
            )
        # Learning: comment monitor — check for replies
        monitor_hours = int(cfg_get("learning.comment_monitor_interval_hours", 4))
        if cfg_get("learning.enabled", True):
            self._scheduler.add_job(
                _job_comment_monitor,
                IntervalTrigger(hours=monitor_hours, jitter=600),
                id="comment_monitor",
                replace_existing=True,
            )
        # Learning: auto-tuner — adjust thresholds
        if cfg_get("learning.auto_tune_enabled", False):
            self._scheduler.add_job(
                _job_auto_tune,
                IntervalTrigger(hours=24, jitter=3600),
                id="auto_tune",
                replace_existing=True,
            )
        # Content intelligence: extract insights from research snippets
        extraction_hours = int(cfg_get("content_intelligence.extraction_interval_hours", 4))
        extraction_jitter = int(cfg_get("content_intelligence.extraction_jitter_seconds", 1200))
        if cfg_get("content_intelligence.enabled", True):
            self._scheduler.add_job(
                _job_content_extraction,
                IntervalTrigger(hours=extraction_hours, jitter=extraction_jitter),
                id="content_extraction",
                replace_existing=True,
            )
        logger.info(
            f"Scheduler: default jobs registered "
            f"(feed_scan every {interval} min ±{feed_jitter}s, hourly_reset, budget_reset, "
            f"campaign_processing every 30 min ±180s, post_publishing every 1 min, "
            f"topic_rotation every {cycle_hours} h ±1800s, "
            f"topic_research every {research_hours} h ±600s, "
            f"comment_monitor every {monitor_hours} h, auto_tune every 24h)"
        )


# ── Scheduled job functions (module-level so APScheduler can pickle them) ──

def _job_feed_scan():
    """Dispatches a feed-scan task to the engine worker pool."""
    logger.info("Scheduler: feed_scan fired")
    try:
        from backend.core.engine import get_engine
        eng = get_engine()
        if eng is not None:
            eng.queue_feed_scan()
    except Exception as exc:
        logger.warning(f"Scheduler: feed_scan dispatch error: {exc}")


def _job_hourly_reset():
    """Resets rate-limiter sliding windows at the top of each hour."""
    logger.info("Scheduler: hourly_reset fired")
    try:
        from backend.core.engine import get_engine
        eng = get_engine()
        if eng is not None:
            eng.rate_limiter.reset_hour()
    except Exception as exc:
        logger.warning(f"Scheduler: hourly_reset error: {exc}")


def _job_budget_reset():
    """Resets all daily budget counters at midnight."""
    logger.info("Scheduler: budget_reset fired")
    try:
        from backend.storage.database import get_db
        from backend.storage import budget_tracker
        with get_db() as db:
            budget_tracker.reset_all(db)
    except Exception as exc:
        logger.warning(f"Scheduler: budget_reset error: {exc}")


def _job_campaign_processing():
    """Dispatches campaign processing to the engine worker pool."""
    logger.info("Scheduler: campaign_processing fired")
    try:
        from backend.growth.campaign_engine import run_campaign_processing
        from backend.core.engine import get_engine
        eng = get_engine()
        if eng is not None:
            eng.worker_pool.submit(run_campaign_processing)
        else:
            run_campaign_processing()
    except Exception as exc:
        logger.warning(f"Scheduler: campaign_processing error: {exc}")


def _job_post_publishing():
    """
    Check for SCHEDULED posts whose scheduled_at is due and publish them.
    Runs every minute. Skips if engine is not RUNNING or content_studio module disabled.
    """
    try:
        from backend.utils.config_loader import get as _cfg
        if not _cfg("modules.content_studio", True):
            return

        from backend.core.engine import get_engine
        from backend.core.state_manager import EngineState
        eng = get_engine()
        if eng is None or eng.state_manager.get() != EngineState.RUNNING:
            return

        from datetime import datetime, timezone
        from backend.storage.database import get_db
        from backend.storage.models import ScheduledPost

        now = datetime.now(timezone.utc)
        with get_db() as db:
            due_posts = (
                db.query(ScheduledPost)
                .filter(
                    ScheduledPost.status == "SCHEDULED",
                    ScheduledPost.scheduled_at <= now,
                )
                .all()
            )

        if not due_posts:
            return

        logger.info(f"Scheduler: {len(due_posts)} post(s) due for publishing")

        from backend.api.content import _publish_single
        for post in due_posts:
            eng.worker_pool.submit(_publish_single, post.id, post.text)

    except Exception as exc:
        logger.warning(f"Scheduler: post_publishing error: {exc}")


def _job_topic_research():
    """Runs topic research pipeline — fetches from Reddit, RSS, HN, LinkedIn feed data."""
    logger.info("Scheduler: topic_research fired")
    try:
        import asyncio
        from backend.utils.config_loader import get as _cfg
        from backend.storage.database import get_db
        from backend.research.topic_researcher import TopicResearcher
        from backend.ai.prompt_loader import PromptLoader

        topics = _cfg("topics", []) or []
        if not topics:
            logger.info("Scheduler: topic_research skipped — no topics configured")
            return

        # Build background AI client for subtopic extraction and scoring
        from backend.ai.client_factory import build_ai_client
        ai_client = build_ai_client("background")
        if ai_client is None:
            logger.info("Scheduler: topic_research — no AI client available, running with heuristic fallback")

        prompt_loader = None
        try:
            prompt_loader = PromptLoader()
            prompt_loader.load_all()
        except Exception as e:
            logger.warning(f"Scheduler: topic_research — failed to load prompts: {e}")

        researcher = TopicResearcher(groq_client=ai_client, prompt_loader=prompt_loader)

        with get_db() as db:
            results = asyncio.run(researcher.research_topics(topics, db))

        try:
            from backend.api.websocket import schedule_broadcast
            schedule_broadcast("research_complete", {
                "topics_researched": len(results),
                "top_topic": results[0]["topic"] if results else None,
            })
        except Exception:
            pass

        logger.info(f"Scheduler: topic_research complete — {len(results)} topics scored")
    except Exception as exc:
        logger.warning(f"Scheduler: topic_research error: {exc}")


def _job_topic_rotation():
    """Runs the topic auto-rotation cycle. Fires every cycle_interval_hours (default 24h)."""
    logger.info("Scheduler: topic_rotation fired")
    try:
        from backend.growth.topic_rotator import topic_rotator
        from backend.storage.database import get_db
        from backend.api.websocket import schedule_broadcast

        with get_db() as db:
            report = topic_rotator.run_iteration_cycle(db)

        schedule_broadcast("topic_rotation", report)
        logger.info(
            f"Scheduler: topic rotation complete — "
            f"activated: {report['topics_activated']}, "
            f"paused: {report['topics_paused']}, "
            f"active: {report['active_count']}"
        )
    except Exception as exc:
        logger.warning(f"Scheduler: topic_rotation error: {exc}")


def _job_comment_monitor():
    """Check recent comments for replies — feeds self-learning loop."""
    logger.info("Scheduler: comment_monitor fired")
    try:
        from backend.core.engine import get_engine
        from backend.core.state_manager import EngineState
        eng = get_engine()
        if eng is None or eng.state_manager.get() != EngineState.RUNNING:
            return
        from backend.learning.comment_monitor import run_comment_monitor
        run_comment_monitor()
    except Exception as exc:
        logger.warning(f"Scheduler: comment_monitor error: {exc}")


def _job_auto_tune():
    """Auto-adjust scoring thresholds and schedule based on engagement data."""
    logger.info("Scheduler: auto_tune fired")
    try:
        from backend.learning.auto_tuner import job_auto_tune
        job_auto_tune()
    except Exception as exc:
        logger.warning(f"Scheduler: auto_tune error: {exc}")


def _job_content_extraction():
    """Extract structured insights from unprocessed research snippets."""
    logger.info("Scheduler: content_extraction fired")
    try:
        import asyncio
        from backend.utils.config_loader import get as _cfg
        from backend.storage.database import get_db
        from backend.research.content_extractor import ContentExtractor
        from backend.research.pattern_aggregator import PatternAggregator
        from backend.ai.prompt_loader import PromptLoader

        # Build background AI client for extraction
        from backend.ai.client_factory import build_ai_client
        ai_client = build_ai_client("background")
        if ai_client is None:
            logger.info("Scheduler: content_extraction skipped — no AI key configured")
            return

        prompt_loader = None
        try:
            prompt_loader = PromptLoader()
            prompt_loader.load_all()
        except Exception as e:
            logger.warning(f"Scheduler: content_extraction — failed to load prompts: {e}")
            return

        extractor = ContentExtractor(groq_client=ai_client, prompt_loader=prompt_loader)
        agg = PatternAggregator()

        batch_size = int(_cfg("content_intelligence.extraction_batch_size", 20))
        with get_db() as db:
            insights = asyncio.run(extractor.extract_from_snippets(db, batch_size=batch_size))

        if insights:
            with get_db() as db:
                agg.aggregate_patterns(db)

        try:
            from backend.api.websocket import schedule_broadcast
            schedule_broadcast("extraction_complete", {
                "insights_created": len(insights),
            })
        except Exception:
            pass

        logger.info(f"Scheduler: content_extraction complete — {len(insights)} insights created")
    except Exception as exc:
        logger.warning(f"Scheduler: content_extraction error: {exc}")
