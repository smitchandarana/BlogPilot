"""
Prompt file loader with hot-reload support.

Reads prompt templates from prompts/*.txt.
Variables are denoted {variable_name} in templates.

Usage:
    loader = PromptLoader()
    loader.load_all()
    text = loader.format("comment", post_text=..., author_name=..., topics=..., tone=...)
"""
import os
import re
import shutil
import threading
from typing import Dict, List, Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

from backend.utils.logger import get_logger

logger = get_logger(__name__)

_PROMPTS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "prompts")
)
_PROMPT_NAMES = ["relevance", "comment", "post", "note", "reply", "comment_candidate", "comment_scorer", "post_scorer", "post_with_context", "topic_scorer", "topic_extractor", "content_extractor", "structured_post"]

_VAR_RE = re.compile(r"\{(\w+)\}")


class _ReloadHandler(FileSystemEventHandler):
    def __init__(self, loader: "PromptLoader"):
        self._loader = loader

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(".txt"):
            logger.info(f"PromptLoader: detected change in {event.src_path} — reloading")
            self._loader.load_all()


class PromptLoader:
    """
    Loads and caches prompt templates from prompts/*.txt.

    Thread-safe. Multiple instances are safe (each has its own cache).
    Call load_all() before first use.
    """

    def __init__(self):
        self._prompts: Dict[str, str] = {}
        self._lock = threading.Lock()
        self._observer: Optional[Observer] = None

    # ── Loading ──────────────────────────────────────────────────────────

    def load_all(self) -> None:
        """Read all prompt .txt files from the prompts/ directory."""
        loaded = {}
        for name in _PROMPT_NAMES:
            path = os.path.join(_PROMPTS_DIR, f"{name}.txt")
            try:
                with open(path, "r", encoding="utf-8") as f:
                    loaded[name] = f.read()
            except FileNotFoundError:
                logger.warning(f"PromptLoader: {path} not found — using empty string")
                loaded[name] = ""
            except Exception as e:
                logger.error(f"PromptLoader: failed to read {path}: {e}")
                loaded[name] = ""

        with self._lock:
            self._prompts = loaded
        logger.info(f"PromptLoader: loaded {len(loaded)} prompts from {_PROMPTS_DIR}")

    # ── Access ───────────────────────────────────────────────────────────

    def get(self, name: str) -> str:
        """Return raw template text for prompt *name*."""
        with self._lock:
            if name not in self._prompts:
                raise KeyError(f"Prompt '{name}' not loaded. Call load_all() first.")
            return self._prompts[name]

    def format(self, prompt_name: str, **kwargs) -> str:
        """
        Fill {variables} in the template and return the formatted string.
        Uses safe substitution: unresolved placeholders are left as-is
        (handles accidental single-brace JSON in prompts without crashing).
        """
        template = self.get(prompt_name)
        try:
            return template.format_map(kwargs)
        except KeyError:
            # Fallback: replace only known variables, leave everything else intact.
            # This prevents a broken prompt from crashing the entire pipeline.
            result = template
            for key, value in kwargs.items():
                result = result.replace("{" + key + "}", str(value))
            logger.warning(
                f"PromptLoader: format_map failed for '{prompt_name}' — "
                f"used manual substitution (prompt may have unescaped braces)"
            )
            return result

    def get_variables(self, prompt_name: str) -> List[str]:
        """Return list of {variable} names found in the template."""
        template = self.get(prompt_name)
        return list(dict.fromkeys(_VAR_RE.findall(template)))  # deduplicated, order preserved

    # ── Hot-reload ───────────────────────────────────────────────────────

    def watch(self) -> None:
        """Start a watchdog observer to reload prompts on file change."""
        if self._observer and self._observer.is_alive():
            return
        handler = _ReloadHandler(self)
        self._observer = Observer()
        self._observer.schedule(handler, _PROMPTS_DIR, recursive=False)
        self._observer.start()
        logger.info(f"PromptLoader: watching {_PROMPTS_DIR} for changes")

    def stop_watch(self) -> None:
        """Stop the watchdog observer."""
        if self._observer and self._observer.is_alive():
            self._observer.stop()
            self._observer.join()

    # ── Default reset ────────────────────────────────────────────────────

    def reset_to_default(self, name: str) -> str:
        """
        Copy {name}.txt.default → {name}.txt and reload.
        Returns the default text.
        Raises FileNotFoundError if no .default file exists.
        """
        default_path = os.path.join(_PROMPTS_DIR, f"{name}.txt.default")
        live_path = os.path.join(_PROMPTS_DIR, f"{name}.txt")
        if not os.path.exists(default_path):
            raise FileNotFoundError(f"No default found for prompt '{name}': {default_path}")
        shutil.copy2(default_path, live_path)
        self.load_all()
        return self.get(name)
