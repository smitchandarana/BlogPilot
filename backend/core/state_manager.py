import threading
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, List, Optional

from backend.utils.logger import get_logger

logger = get_logger(__name__)


class EngineState(Enum):
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    ERROR = "ERROR"


_VALID_TRANSITIONS: dict[EngineState, set] = {
    EngineState.STOPPED: {EngineState.RUNNING},
    EngineState.RUNNING: {EngineState.PAUSED, EngineState.STOPPED, EngineState.ERROR},
    EngineState.PAUSED:  {EngineState.RUNNING, EngineState.STOPPED},
    EngineState.ERROR:   {EngineState.STOPPED},
}


class StateManager:
    """Singleton engine state machine. All transitions go through here."""

    _instance: Optional["StateManager"] = None
    _class_lock = threading.Lock()

    def __new__(cls) -> "StateManager":
        if cls._instance is None:
            with cls._class_lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._state = EngineState.STOPPED
                    inst._entered_at = datetime.now(timezone.utc)
                    inst._last_error: Optional[str] = None
                    inst._lock = threading.Lock()
                    inst._callbacks: List[Callable] = []
                    cls._instance = inst
        return cls._instance

    # ── Reads ──────────────────────────────────────────────────────────────

    def get(self) -> EngineState:
        with self._lock:
            return self._state

    def get_info(self) -> dict:
        with self._lock:
            return {
                "state": self._state.value,
                "entered_at": self._entered_at.isoformat(),
                "last_error": self._last_error,
            }

    # ── Transitions ────────────────────────────────────────────────────────

    def transition(self, new_state: EngineState, error_reason: str = None):
        callbacks_to_fire: List[Callable] = []

        with self._lock:
            allowed = _VALID_TRANSITIONS.get(self._state, set())
            if new_state not in allowed:
                raise ValueError(
                    f"Invalid transition: {self._state.value} → {new_state.value}"
                )
            old = self._state
            self._state = new_state
            self._entered_at = datetime.now(timezone.utc)

            if error_reason:
                self._last_error = error_reason
            elif new_state == EngineState.RUNNING:
                self._last_error = None

            callbacks_to_fire = list(self._callbacks)

        logger.info(f"Engine state: {old.value} → {new_state.value}")

        for cb in callbacks_to_fire:
            try:
                cb(new_state)
            except Exception as exc:
                logger.warning(f"State-change callback error: {exc}")

    # ── Convenience wrappers ───────────────────────────────────────────────

    def start(self):
        self.transition(EngineState.RUNNING)

    def stop(self):
        self.transition(EngineState.STOPPED)

    def pause(self):
        self.transition(EngineState.PAUSED)

    def resume(self):
        self.transition(EngineState.RUNNING)

    def set_error(self, reason: str):
        self.transition(EngineState.ERROR, error_reason=reason)

    def recover(self):
        """Reset from ERROR → STOPPED so the engine can be restarted."""
        self.transition(EngineState.STOPPED)

    # ── Callback registration ──────────────────────────────────────────────

    def on_change(self, callback: Callable[[EngineState], None]):
        """Register a callback fired synchronously on every state transition."""
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def remove_callback(self, callback: Callable):
        with self._lock:
            self._callbacks = [c for c in self._callbacks if c is not callback]
