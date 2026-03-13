import os
import fcntl
import tempfile
import signal
import atexit

from backend.utils.logger import get_logger

logger = get_logger(__name__)

_LOCK_PATH = os.path.join(tempfile.gettempdir(), "linkedin_engine.lock")
_lock_fd = None


def acquire() -> bool:
    """Acquire single-instance lock using fcntl.flock (no TOCTOU race)."""
    global _lock_fd

    # Verify path is not a symlink
    if os.path.islink(_LOCK_PATH):
        logger.error(f"Lock path is a symlink — refusing to acquire: {_LOCK_PATH}")
        return False

    try:
        _lock_fd = open(_LOCK_PATH, "w")
        fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_fd.write(str(os.getpid()))
        _lock_fd.flush()

        # Register cleanup handlers
        atexit.register(release)
        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)

        logger.info(f"Lock acquired (PID {os.getpid()})")
        return True
    except (IOError, OSError) as e:
        logger.warning(f"Failed to acquire lock (another instance running?): {e}")
        if _lock_fd:
            _lock_fd.close()
            _lock_fd = None
        return False


def release():
    """Release the flock and remove the lock file."""
    global _lock_fd
    if _lock_fd:
        try:
            fcntl.flock(_lock_fd, fcntl.LOCK_UN)
            _lock_fd.close()
        except Exception:
            pass
        _lock_fd = None
    if os.path.exists(_LOCK_PATH) and not os.path.islink(_LOCK_PATH):
        try:
            os.remove(_LOCK_PATH)
            logger.info("Lock file released")
        except OSError as e:
            logger.warning(f"Failed to remove lock file: {e}")


def is_locked() -> bool:
    """Check if the lock file exists and is held by another process."""
    if not os.path.exists(_LOCK_PATH):
        return False
    if os.path.islink(_LOCK_PATH):
        return False
    try:
        fd = open(_LOCK_PATH, "r")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # If we got the lock, it wasn't held — release immediately
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()
        return False
    except (IOError, OSError):
        return True


def _signal_handler(signum, frame):
    logger.info(f"Signal {signum} received — releasing lock and exiting")
    release()
    raise SystemExit(0)
