"""
Centralized path resolution for both development and PyInstaller frozen mode.

- get_base_dir(): Where read-only bundled files live (prompts, config template, ui/dist).
  In dev: project root.  In frozen: sys._MEIPASS (temp extract dir).

- get_data_dir(): Where writable runtime files live (data/, logs/, config/.secrets/).
  In dev: project root.  In frozen: directory containing the EXE.
"""

import os
import sys


def is_frozen() -> bool:
    """True when running inside a PyInstaller bundle."""
    return getattr(sys, "frozen", False)


def get_base_dir() -> str:
    """
    Root for read-only bundled assets (prompts/, config/settings.yaml, ui/dist/).
    PyInstaller extracts these into sys._MEIPASS at runtime.
    """
    if is_frozen():
        return sys._MEIPASS
    # Dev mode: project root is two levels up from backend/utils/
    return os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))


def get_data_dir() -> str:
    """
    Root for writable runtime data (data/, logs/, config/.secrets/, browser_profile/).
    In frozen mode this is the folder containing the EXE so files persist across runs.
    """
    if is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
