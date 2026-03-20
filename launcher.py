"""
BlogPilot Launcher — Entry point for both dev mode and PyInstaller EXE.

Starts the FastAPI/uvicorn backend and opens the loading page in the browser.
The loading page is served by FastAPI and auto-redirects to the main app once
the backend is fully up. No console window is shown to end users.
"""

import os
import sys
import threading
import time
import webbrowser

# Ensure project root is importable
if getattr(sys, "frozen", False):
    # PyInstaller frozen mode: _MEIPASS contains the bundled files
    sys.path.insert(0, sys._MEIPASS)
    _ROOT = os.path.dirname(sys.executable)
else:
    _ROOT = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, _ROOT)


def _fix_stdio():
    """
    In windowed PyInstaller builds (console=False), sys.stdout and sys.stderr
    are None. Uvicorn's log formatter calls sys.stdout.isatty() at startup,
    which raises AttributeError: 'NoneType' has no attribute 'isatty'.

    Fix: redirect stdout/stderr to a log file next to the EXE so they are
    real file objects (isatty() returns False for files, which is correct).
    """
    if sys.stdout is not None:
        return  # console is available — nothing to do

    log_dir = os.path.join(_ROOT, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "launcher.log")
    # Open in append mode; rotate manually if it exceeds 5 MB
    try:
        if os.path.isfile(log_path) and os.path.getsize(log_path) > 5 * 1024 * 1024:
            os.replace(log_path, log_path + ".1")
    except OSError:
        pass
    _fh = open(log_path, "a", encoding="utf-8", errors="replace")
    sys.stdout = _fh
    sys.stderr = _fh


_fix_stdio()


HOST = "127.0.0.1"
PORT = 8000
BASE_URL = f"http://{HOST}:{PORT}"


def _wait_and_open_browser():
    """Poll /health until the server is up, then open the main UI."""
    import urllib.request

    for _ in range(60):           # wait up to 30 seconds
        time.sleep(0.5)
        try:
            urllib.request.urlopen(f"{BASE_URL}/health", timeout=2)
            webbrowser.open(BASE_URL)
            return
        except Exception:
            continue

    # Server didn't respond in time — open anyway so user can see the error
    webbrowser.open(BASE_URL)


def _set_data_dirs():
    """
    In frozen mode, make sure writable data directories (DB, logs, secrets, config)
    are located next to the EXE (not inside the read-only _MEIPASS bundle).
    """
    if not getattr(sys, "frozen", False):
        return

    # Point config_loader and database to EXE-adjacent paths
    os.environ.setdefault("BLOGPILOT_ROOT", _ROOT)


def main():
    _set_data_dirs()

    # Open browser in the background once the server is ready
    t = threading.Thread(target=_wait_and_open_browser, daemon=True)
    t.start()

    # Start uvicorn (blocking — this keeps the process alive)
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="warning",    # Quieter logs for end-user EXE
    )


if __name__ == "__main__":
    main()
