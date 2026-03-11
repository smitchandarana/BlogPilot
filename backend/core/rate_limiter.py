import threading
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Dict

from backend.utils.config_loader import get as cfg_get
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Maps action type → config key → default value
_LIMIT_MAP: Dict[str, tuple] = {
    "likes":          ("rate_limits.likes_per_hour",        8),
    "comments":       ("rate_limits.comments_per_hour",     4),
    "connections":    ("rate_limits.connections_per_hour",  5),
    "profile_visits": ("rate_limits.profile_visits_per_hour", 15),
    "posts_published": ("rate_limits.posts_per_hour",       2),
}


class RateLimiter:
    """In-memory sliding-window rate limiter. One window per action type, 1-hour horizon."""

    def __init__(self):
        self._lock = threading.Lock()
        # deque of Unix timestamps (float) per action type
        self._windows: Dict[str, deque] = defaultdict(deque)

    # ── Helpers ────────────────────────────────────────────────────────────

    def _get_limit(self, action_type: str) -> int:
        cfg_key, default = _LIMIT_MAP.get(action_type, (None, 10))
        if cfg_key:
            return int(cfg_get(cfg_key, default))
        return default

    def _purge_old(self, window: deque):
        """Remove entries older than 1 hour."""
        cutoff = datetime.now(timezone.utc).timestamp() - 3600.0
        while window and window[0] < cutoff:
            window.popleft()

    # ── Public API ─────────────────────────────────────────────────────────

    def check(self, action_type: str) -> bool:
        """Return True if the action is under the hourly cap (OK to proceed)."""
        with self._lock:
            window = self._windows[action_type]
            self._purge_old(window)
            limit = self._get_limit(action_type)
            under = len(window) < limit
            if not under:
                logger.info(
                    f"Rate limit reached: {action_type} {len(window)}/{limit}/hr"
                )
            return under

    def increment(self, action_type: str):
        """Record one usage of action_type now."""
        with self._lock:
            self._windows[action_type].append(datetime.now(timezone.utc).timestamp())
            logger.debug(
                f"Rate limiter: {action_type} → {len(self._windows[action_type])} in window"
            )

    def reset_hour(self):
        """Clear all windows — called at top of each hour by scheduler."""
        with self._lock:
            self._windows.clear()
        logger.info("Rate limiter: hourly windows reset")

    def get_counts(self) -> dict:
        """Return current counts and limits for all action types."""
        with self._lock:
            result = {}
            for action_type, window in self._windows.items():
                self._purge_old(window)
                result[action_type] = {
                    "count": len(window),
                    "limit": self._get_limit(action_type),
                }
            return result
