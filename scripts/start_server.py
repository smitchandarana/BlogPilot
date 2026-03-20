"""
Server startup helper — used by server.py restart logic.

Filters sys.path to remove any uvicorn package subdirectory that Python 3.14
may inject into the child process environment, which causes uvicorn's logging.py
to shadow the stdlib logging module (AttributeError: module 'logging' has no
attribute 'Formatter').
"""
import sys
import os

# Ensure project root is on path
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

# Remove any uvicorn package sub-directory that may shadow stdlib logging
sys.path = [p for p in sys.path if not p.rstrip("/\\").endswith("uvicorn")]

import uvicorn

uvicorn.run("backend.main:app", host="127.0.0.1", port=8000)
