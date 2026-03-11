import threading
from collections import deque
from datetime import datetime, timezone
from typing import Optional

from backend.utils.config_loader import get as cfg_get
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class CircuitBreaker:
    """
    Rolling-window error tracker. Trips the engine into PAUSED (or ERROR) state
    when too many errors occur within a configured time window.
    """

    def __init__(self, state_manager=None):
        self._lock = threading.Lock()
        self._errors: deque = deque()   # deque of Unix timestamps
        self._state_manager = state_manager
        self._tripped: bool = False

    # ── Config helpers ─────────────────────────────────────────────────────

    def _threshold(self) -> int:
        return int(cfg_get("circuit_breaker.error_threshold", 3))

    def _window_seconds(self) -> float:
        return float(cfg_get("circuit_breaker.window_minutes", 10)) * 60.0

    def _captcha_action(self) -> str:
        return cfg_get("circuit_breaker.captcha_detected_action", "pause")

    def _enabled(self) -> bool:
        return bool(cfg_get("circuit_breaker.enabled", True))

    # ── Window management ──────────────────────────────────────────────────

    def _purge_old(self):
        cutoff = datetime.now(timezone.utc).timestamp() - self._window_seconds()
        while self._errors and self._errors[0] < cutoff:
            self._errors.popleft()

    # ── Public API ─────────────────────────────────────────────────────────

    def record_error(self, source: str = "unknown"):
        """Record an error. If threshold is reached, trip the circuit breaker."""
        if not self._enabled():
            return

        trip_now = False
        stop_instead_of_pause = False

        with self._lock:
            self._errors.append(datetime.now(timezone.utc).timestamp())
            self._purge_old()
            count = len(self._errors)
            threshold = self._threshold()
            logger.warning(
                f"CircuitBreaker error [{source}]: {count}/{threshold} "
                f"in {cfg_get('circuit_breaker.window_minutes', 10)} min"
            )
            if count >= threshold and not self._tripped:
                self._tripped = True
                trip_now = True
                is_captcha = "captcha" in source.lower()
                stop_instead_of_pause = is_captcha and self._captcha_action() == "stop"

        if trip_now:
            self._trip(source, stop=stop_instead_of_pause)

    def record_success(self):
        """Reset tripped flag on a successful action."""
        with self._lock:
            self._tripped = False

    def is_open(self) -> bool:
        """True when the circuit is tripped (engine should not act)."""
        with self._lock:
            return self._tripped

    def reset(self):
        """Manually reset circuit breaker after investigation."""
        with self._lock:
            self._errors.clear()
            self._tripped = False
        logger.info("CircuitBreaker manually reset")

    # ── Trip logic ─────────────────────────────────────────────────────────

    def _trip(self, source: str, stop: bool = False):
        logger.error(f"CircuitBreaker TRIPPED — source: {source}")

        # Broadcast alert to UI
        try:
            from backend.api.websocket import schedule_broadcast
            schedule_broadcast("alert", {
                "level": "critical",
                "message": f"Circuit breaker tripped: {source}",
            })
        except Exception as exc:
            logger.warning(f"CircuitBreaker: broadcast failed: {exc}")

        # Transition engine state
        if self._state_manager is None:
            return

        try:
            from backend.core.state_manager import EngineState
            current = self._state_manager.get()
            if current == EngineState.RUNNING:
                if stop:
                    self._state_manager.set_error(source)
                else:
                    self._state_manager.pause()
        except Exception as exc:
            logger.error(f"CircuitBreaker: state transition failed: {exc}")
