import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from queue import PriorityQueue, Empty
from typing import Any, Optional

from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(order=True)
class Task:
    """A unit of work. Ordered by (priority, created_at) for PriorityQueue."""

    priority: int
    created_at: datetime = field(
        compare=True,
        default_factory=lambda: datetime.now(timezone.utc),
    )
    # Non-ordering fields
    id: str = field(compare=False, default_factory=lambda: str(uuid.uuid4()))
    type: str = field(compare=False, default="")
    payload: dict = field(compare=False, default_factory=dict)
    retries: int = field(compare=False, default=0)


class TaskQueue:
    """Priority queue wrapper. Lower priority number = higher urgency (1 is highest)."""

    def __init__(self, maxsize: int = 100):
        self._q: PriorityQueue = PriorityQueue(maxsize=maxsize)

    def put(self, task_type: str, payload: Any = None, priority: int = 5) -> Task:
        """Create and enqueue a Task. Returns the created Task."""
        task = Task(priority=priority, type=task_type, payload=payload or {})
        self._q.put(task)
        logger.debug(f"Task queued: {task_type} (priority={priority}, id={task.id})")
        return task

    def get(self) -> Optional[Task]:
        """Non-blocking dequeue. Returns None if queue is empty."""
        try:
            return self._q.get_nowait()
        except Empty:
            return None

    def get_blocking(self, timeout: float = 1.0) -> Optional[Task]:
        """Blocking dequeue with timeout. Returns None on timeout."""
        try:
            return self._q.get(timeout=timeout)
        except Empty:
            return None

    def size(self) -> int:
        return self._q.qsize()

    def clear(self):
        """Drain the queue safely."""
        count = 0
        while not self._q.empty():
            try:
                self._q.get_nowait()
                count += 1
            except Empty:
                break
        if count:
            logger.info(f"Task queue cleared: {count} tasks discarded")

    def is_empty(self) -> bool:
        return self._q.empty()
