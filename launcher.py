"""
BlogPilot Launcher — Entry point for both dev mode and PyInstaller EXE.

Starts the FastAPI/uvicorn server and opens the UI in the default browser.
When frozen (EXE), runs without a console window.
"""

import os
import sys
import threading
import time
import webbrowser

# Ensure project root is importable
if getattr(sys, "frozen", False):
    # PyInstaller: _MEIPASS has the bundled code
    sys.path.insert(0, sys._MEIPASS)
else:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"


def _open_browser():
    """Wait for server to start, then open the browser."""
    import urllib.request
    for _ in range(30):  # try for up to 15 seconds
        time.sleep(0.5)
        try:
            urllib.request.urlopen(f"{URL}/health", timeout=2)
            webbrowser.open(URL)
            return
        except Exception:
            continue
    # If we get here, server didn't start in time — open anyway
    webbrowser.open(URL)


def main():
    # Launch browser opener in background thread
    t = threading.Thread(target=_open_browser, daemon=True)
    t.start()

    # Start uvicorn (blocking)
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
