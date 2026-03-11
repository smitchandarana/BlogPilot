import os
import tempfile
import signal
import atexit

from backend.utils.logger import get_logger

logger = get_logger(__name__)

_LOCK_PATH = os.path.join(tempfile.gettempdir(), "linkedin_engine.lock")


def acquire() -> bool:
    if is_locked():
        logger.warning(f"Lock file exists and process is alive: {_LOCK_PATH}")
        return False

    pid = os.getpid()
    try:
        with open(_LOCK_PATH, "w") as f:
            f.write(str(pid))
        logger.info(f"Lock acquired (PID {pid})")

        # Register cleanup handlers
        atexit.register(release)
        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)

        return True
    except OSError as e:
        logger.error(f"Failed to acquire lock: {e}")
        return False


def release():
    if os.path.exists(_LOCK_PATH):
        try:
            os.remove(_LOCK_PATH)
            logger.info("Lock file released")
        except OSError as e:
            logger.warning(f"Failed to remove lock file: {e}")


def is_locked() -> bool:
    if not os.path.exists(_LOCK_PATH):
        return False
    try:
        with open(_LOCK_PATH, "r") as f:
            pid = int(f.read().strip())
        # Check if PID is alive
        os.kill(pid, 0)
        return True
    except (ValueError, ProcessLookupError, PermissionError):
        # PID not alive or invalid — stale lock
        try:
            os.remove(_LOCK_PATH)
        except OSError:
            pass
        return False
    except OSError:
        return False


def _signal_handler(signum, frame):
    logger.info(f"Signal {signum} received — releasing lock and exiting")
    release()
    raise SystemExit(0)
