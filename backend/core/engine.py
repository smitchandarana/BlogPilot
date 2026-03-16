import time
import threading
from typing import Optional

from backend.utils.logger import get_logger
from backend.utils.config_loader import get as cfg_get
from backend.core.state_manager import StateManager, EngineState
from backend.core.task_queue import TaskQueue
from backend.core.worker_pool import WorkerPool
from backend.core.rate_limiter import RateLimiter
from backend.core.circuit_breaker import CircuitBreaker
from backend.core.scheduler import Scheduler

logger = get_logger(__name__)

_engine_instance: Optional["Engine"] = None
_engine_lock = threading.Lock()


class Engine:
    """
    Master engine class. Owns and wires all core modules together.
    Do not instantiate directly — use get_engine() or init_engine().
    """

    def __init__(self):
        self.state_manager = StateManager()
        self.task_queue = TaskQueue(
            maxsize=int(cfg_get("workers.queue_max_size", 100))
        )
        self.worker_pool = WorkerPool(state_manager=self.state_manager)
        self.rate_limiter = RateLimiter()
        self.circuit_breaker = CircuitBreaker(state_manager=self.state_manager)
        self.scheduler = Scheduler()

        self._start_time: Optional[float] = None

        # Register state-change → WebSocket broadcast
        self.state_manager.on_change(self._on_state_change)

        logger.info("Engine initialised")

    # ── State callbacks ────────────────────────────────────────────────────

    def _on_state_change(self, new_state: EngineState):
        try:
            from backend.api.websocket import schedule_broadcast
            schedule_broadcast("engine_state", {"state": new_state.value})
        except Exception as exc:
            logger.warning(f"Engine: state-change broadcast failed: {exc}")

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def start(self):
        """Start the engine: validate state, start scheduler, transition to RUNNING."""
        current = self.state_manager.get()
        if current != EngineState.STOPPED:
            raise ValueError(
                f"Cannot start from state {current.value} — stop the engine first"
            )
        logger.info("Engine starting…")
        # Reset stale budget counters if midnight cron was missed, then sync from ActionLog
        try:
            from backend.storage.database import get_db
            from backend.storage import budget_tracker
            with get_db() as db:
                budget_tracker.reset_if_stale(db)
                budget_tracker.sync_from_actions(db)
        except Exception as exc:
            logger.warning(f"Engine: budget stale-check failed: {exc}")
        # Run auto-tuner if stale (>24h since last tune)
        try:
            from backend.storage.database import get_db
            from backend.learning.auto_tuner import tune_if_stale
            with get_db() as db:
                tune_if_stale(db)
        except Exception as exc:
            logger.warning(f"Engine: auto-tune stale-check failed: {exc}")
        self._start_time = time.time()
        self.state_manager.start()          # STOPPED → RUNNING
        self.scheduler.start()
        logger.info("Engine RUNNING")

    def stop(self):
        """Stop the engine: stop scheduler first, transition, then drain workers."""
        current = self.state_manager.get()
        if current not in (EngineState.RUNNING, EngineState.PAUSED, EngineState.ERROR):
            raise ValueError(
                f"Cannot stop from state {current.value}"
            )
        logger.info("Engine stopping…")
        self.circuit_breaker.cancel_pending_resume()  # cancel any auto-resume timer
        self.scheduler.stop()               # stop new jobs from firing first
        self.state_manager.stop()           # → STOPPED
        self.worker_pool.drain()            # wait for in-flight tasks
        self._start_time = None
        logger.info("Engine STOPPED")

    def pause(self):
        """Pause: scheduler stops firing jobs, workers finish current tasks then idle."""
        current = self.state_manager.get()
        if current != EngineState.RUNNING:
            raise ValueError(
                f"Cannot pause from state {current.value} — engine must be RUNNING"
            )
        logger.info("Engine pausing…")
        self.state_manager.pause()          # RUNNING → PAUSED
        self.scheduler.pause()
        logger.info("Engine PAUSED")

    def resume(self):
        """Resume from PAUSED back to RUNNING."""
        current = self.state_manager.get()
        if current != EngineState.PAUSED:
            raise ValueError(
                f"Cannot resume from state {current.value} — engine must be PAUSED"
            )
        logger.info("Engine resuming…")
        self.state_manager.resume()         # PAUSED → RUNNING
        self.scheduler.resume()
        logger.info("Engine RUNNING")

    # ── Task dispatch ──────────────────────────────────────────────────────

    def queue_feed_scan(self):
        """Submit a feed-scan task to the worker pool (called by scheduler)."""
        from backend.core.pipeline import run_feed_scan
        self.worker_pool.submit(run_feed_scan)

    # ── Status ─────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        uptime = int(time.time() - self._start_time) if self._start_time else 0
        info = self.state_manager.get_info()

        budget_used: dict = {}
        try:
            from backend.storage.database import get_db
            from backend.storage import budget_tracker
            with get_db() as db:
                rows = budget_tracker.get_all(db)
                budget_used = {
                    r.action_type: {"count": r.count_today, "limit": r.limit_per_day}
                    for r in rows
                }
        except Exception:
            pass

        return {
            "state": info["state"],
            "uptime_seconds": uptime,
            "tasks_queued": self.task_queue.size(),
            "active_workers": self.worker_pool.active_count(),
            "budget_used": budget_used,
            "last_error": info.get("last_error"),
        }

    # Alias kept for backwards compat with existing api/engine.py
    def status(self) -> dict:
        return self.get_status()


# ── Singleton factory ──────────────────────────────────────────────────────

def get_engine() -> Optional[Engine]:
    """Return the existing Engine singleton, or None if not yet initialised."""
    return _engine_instance


def init_engine() -> Engine:
    """Create (or return existing) Engine singleton."""
    global _engine_instance
    if _engine_instance is None:
        with _engine_lock:
            if _engine_instance is None:
                _engine_instance = Engine()
                logger.info("Engine singleton created")
    return _engine_instance


# Module-level singleton — created on first import
engine = init_engine()
