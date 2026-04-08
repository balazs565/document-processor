"""Persistent recent-files list stored as JSON."""
import json
import os
from typing import List

import config
from utils.logger import get_logger

logger = get_logger("recent_files")


class RecentFiles:
    def __init__(self, max_items: int = config.MAX_RECENT_FILES):
        self._max = max_items
        self._path = config.RECENT_FILES_PATH
        self._items: List[str] = []
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, file_path: str) -> None:
        """Insert a file at the front; deduplicate and trim."""
        file_path = os.path.normpath(file_path)
        if file_path in self._items:
            self._items.remove(file_path)
        self._items.insert(0, file_path)
        self._items = self._items[: self._max]
        self._save()

    def remove(self, file_path: str) -> None:
        file_path = os.path.normpath(file_path)
        if file_path in self._items:
            self._items.remove(file_path)
            self._save()

    def clear(self) -> None:
        self._items = []
        self._save()

    def get_all(self) -> List[str]:
        """Return only files that still exist on disk."""
        existing = [p for p in self._items if os.path.isfile(p)]
        if len(existing) != len(self._items):
            self._items = existing
            self._save()
        return list(self._items)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        try:
            if os.path.exists(self._path):
                with open(self._path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    if isinstance(data, list):
                        self._items = data
        except Exception as exc:
            logger.warning("Could not load recent files: %s", exc)
            self._items = []

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as fh:
                json.dump(self._items, fh, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.warning("Could not save recent files: %s", exc)
