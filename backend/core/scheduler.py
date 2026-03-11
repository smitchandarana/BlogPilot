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
        db_url = f"sqlite:///{os.path.abspath(_SCHEDULER_DB)}"
        jobstores = {"default": SQLAlchemyJobStore(url=db_url)}
        self._scheduler = BackgroundScheduler(
            jobstores=jobstores,
            job_defaults={"coalesce": True, "max_instances": 1},
        )
        self._started: bool = False

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def start(self):
        if not self._started:
            self._scheduler.start()
            self._started = True
            self._register_default_jobs()
            logger.info("Scheduler started")

    def stop(self):
        if self._started and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            self._started = False
            logger.info("Scheduler stopped")

    def pause(self):
        if self._started and self._scheduler.running:
            self._scheduler.pause()
            logger.info("Scheduler paused — jobs will not fire")

    def resume(self):
        if self._started and self._scheduler.running:
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

        self._scheduler.add_job(
            _job_feed_scan,
            IntervalTrigger(minutes=interval),
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
        logger.info(
            f"Scheduler: default jobs registered "
            f"(feed_scan every {interval} min, hourly_reset, budget_reset)"
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
