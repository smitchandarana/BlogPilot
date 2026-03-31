import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Dict, Optional, Any

from backend.utils.logger import get_logger

logger = get_logger(__name__)

MAX_WORKERS = 3  # HARD CAP — never increase. LinkedIn detection risk.


class WorkerPool:
    """
    Thread pool capped at MAX_WORKERS (3).
    Rejects submissions when the engine is not in RUNNING state.
    """

    def __init__(self, state_manager=None):
        self._state_manager = state_manager
        self._lock = threading.Lock()
        self._active: int = 0
        self._handlers: Dict[str, Callable] = {}
        self._executor = self._new_executor()

    def _new_executor(self) -> ThreadPoolExecutor:
        return ThreadPoolExecutor(
            max_workers=MAX_WORKERS,
            thread_name_prefix="engine-worker",
        )

    # ── Handler registration ───────────────────────────────────────────────

    def register_handler(self, task_type: str, fn: Callable):
        self._handlers[task_type] = fn
        logger.debug(f"WorkerPool: handler registered for task type '{task_type}'")

    # ── Submission ─────────────────────────────────────────────────────────

    def submit(self, fn: Callable, *args, **kwargs) -> Optional[Future]:
        """
        Submit a callable. Returns None (silently) if engine is not RUNNING.
        State check and executor submit are atomic (held under lock).
        """
        with self._lock:
            if self._state_manager is not None:
                from backend.core.state_manager import EngineState
                state = self._state_manager.get()
                if state != EngineState.RUNNING:
                    logger.debug(
                        f"WorkerPool: submit rejected — engine is {state.value}"
                    )
                    return None

            label = getattr(fn, "__name__", None) or getattr(getattr(fn, "func", None), "__name__", "task")
            future = self._executor.submit(self._wrap(fn, label), *args, **kwargs)
            return future

    def submit_task(self, task) -> Optional[Future]:
        """Dispatch a Task object to its registered handler by task.type."""
        handler = self._handlers.get(task.type)
        if handler is None:
            logger.warning(f"WorkerPool: no handler for task type '{task.type}'")
            return None
        return self.submit(handler, task)

    # ── Active count ───────────────────────────────────────────────────────

    def active_count(self) -> int:
        with self._lock:
            return self._active

    # ── Drain + reset ──────────────────────────────────────────────────────

    def drain(self):
        """
        Wait for all in-flight tasks to complete, then recreate the executor
        so the pool is ready for a future restart.
        """
        logger.info("WorkerPool: draining in-flight tasks…")
        self._executor.shutdown(wait=True, cancel_futures=False)
        with self._lock:
            self._active = 0  # safe: shutdown(wait=True) guarantees all tasks done
        self._executor = self._new_executor()
        logger.info("WorkerPool: drained and reset")

    # ── Internal wrapper ───────────────────────────────────────────────────

    def _wrap(self, fn: Callable, name: str = "") -> Callable:
        """Wraps a callable to track active count and log lifecycle."""
        label = name or getattr(fn, "__name__", "task")

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            with self._lock:
                self._active += 1
            logger.debug(f"WorkerPool: task started — {label} (active={self._active})")
            try:
                result = fn(*args, **kwargs)
                logger.debug(f"WorkerPool: task completed — {label}")
                return result
            except Exception as exc:
                logger.error(f"WorkerPool: task failed — {label}: {exc}", exc_info=True)
                raise
            finally:
                with self._lock:
                    self._active -= 1

        wrapped.__name__ = label
        return wrapped
