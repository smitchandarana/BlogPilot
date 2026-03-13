import os
import sys
import tempfile
import signal
import atexit

from backend.utils.logger import get_logger

logger = get_logger(__name__)

_LOCK_PATH = os.path.join(tempfile.gettempdir(), "linkedin_engine.lock")
_lock_fd = None

# fcntl is Unix-only; use msvcrt on Windows
_IS_WINDOWS = sys.platform == "win32"
if _IS_WINDOWS:
    import msvcrt
else:
    import fcntl


def acquire() -> bool:
    """Acquire single-instance lock."""
    global _lock_fd

    # Verify path is not a symlink
    if os.path.islink(_LOCK_PATH):
        logger.error(f"Lock path is a symlink — refusing to acquire: {_LOCK_PATH}")
        return False

    try:
        _lock_fd = open(_LOCK_PATH, "w")
        if _IS_WINDOWS:
            msvcrt.locking(_lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
        else:
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
    """Release the lock and remove the lock file."""
    global _lock_fd
    if _lock_fd:
        try:
            if _IS_WINDOWS:
                try:
                    msvcrt.locking(_lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
                except (IOError, OSError):
                    pass
            else:
                fcntl.flock(_lock_fd, fcntl.LOCK_UN)
            _lock_fd.close()
        except Exception:
            pass
        _lock_fd = None
    # On Windows, lock files can't be deleted while another process holds them.
    # Just unlocking + closing is sufficient — the lock is released either way.
    if not _IS_WINDOWS and os.path.exists(_LOCK_PATH) and not os.path.islink(_LOCK_PATH):
        try:
            os.remove(_LOCK_PATH)
        except OSError:
            pass
    # Only log if streams are still open (avoids "Logging error" noise during
    # interpreter shutdown / pytest teardown when atexit handlers fire).
    import logging as _logging
    if not _logging.root.handlers or not getattr(_logging.root.handlers[0], 'stream', None):
        return
    try:
        if _logging.root.handlers[0].stream and not _logging.root.handlers[0].stream.closed:
            logger.info("Lock file released")
    except (ValueError, OSError, AttributeError):
        pass


def is_locked() -> bool:
    """Check if the lock file exists and is held by another process."""
    if not os.path.exists(_LOCK_PATH):
        return False
    if os.path.islink(_LOCK_PATH):
        return False
    try:
        fd = open(_LOCK_PATH, "r+")
        if _IS_WINDOWS:
            msvcrt.locking(fd.fileno(), msvcrt.LK_NBLCK, 1)
            msvcrt.locking(fd.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()
        return False
    except (IOError, OSError):
        return True


def _signal_handler(signum, frame):
    logger.info(f"Signal {signum} received — releasing lock and exiting")
    release()
    raise SystemExit(0)
