import os
import yaml
import threading
from typing import Any
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from backend.utils.logger import get_logger

logger = get_logger(__name__)

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "settings.yaml")


class _ConfigLoader:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._data = {}
                    cls._instance._observer = None
        return cls._instance

    def load_config(self) -> dict:
        path = os.path.abspath(_CONFIG_PATH)
        try:
            with open(path, "r", encoding="utf-8") as f:
                self._data = yaml.safe_load(f) or {}
            logger.info(f"Config loaded from {path}")
        except FileNotFoundError:
            logger.warning(f"Config file not found: {path}. Using empty config.")
            self._data = {}
        except yaml.YAMLError as e:
            logger.error(f"YAML parse error in config: {e}")
        return self._data

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split(".")
        value = self._data
        for k in keys:
            if not isinstance(value, dict):
                return default
            value = value.get(k)
            if value is None:
                return default
        return value

    def all(self) -> dict:
        return self._data

    def watch(self):
        if self._observer and self._observer.is_alive():
            return

        config_dir = os.path.dirname(os.path.abspath(_CONFIG_PATH))

        class _ReloadHandler(FileSystemEventHandler):
            def __init__(self, loader):
                self._loader = loader

            def on_modified(self, event):
                if not event.is_directory and event.src_path.endswith("settings.yaml"):
                    logger.info("Config file changed — reloading")
                    self._loader.load_config()

        self._observer = Observer()
        self._observer.schedule(_ReloadHandler(self), path=config_dir, recursive=False)
        self._observer.daemon = True
        self._observer.start()
        logger.info("Config file watcher started")

    def save_config(self, updates: dict) -> dict:
        """Deep-merge updates into current config, write back to YAML, reload."""
        self._deep_merge(self._data, updates)
        path = os.path.abspath(_CONFIG_PATH)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self._data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        logger.info(f"Config saved to {path}")
        return self._data

    @staticmethod
    def _deep_merge(base: dict, updates: dict):
        for key, val in updates.items():
            if isinstance(val, dict) and isinstance(base.get(key), dict):
                _ConfigLoader._deep_merge(base[key], val)
            else:
                base[key] = val

    def stop_watch(self):
        if self._observer and self._observer.is_alive():
            self._observer.stop()
            self._observer.join()


_loader = _ConfigLoader()


def load_config() -> dict:
    return _loader.load_config()


def get(key: str, default: Any = None) -> Any:
    return _loader.get(key, default)


def all_config() -> dict:
    return _loader.all()


def watch():
    _loader.watch()


def save_config(updates: dict) -> dict:
    return _loader.save_config(updates)


def stop_watch():
    _loader.stop_watch()
