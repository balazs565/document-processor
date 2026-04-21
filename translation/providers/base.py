"""
Abstract base class for all translation providers.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Tuple


class TranslationProvider(ABC):
    """All providers must implement this interface."""

    name: str = "Unknown"

    @abstractmethod
    def translate(self, text: str, source: str, target: str) -> str:
        """
        Translate *text* from *source* to *target* language.
        Language codes: "en", "ro", "hu", "auto".
        Raises RuntimeError on failure.
        """

    def translate_batch(self, texts: List[str], source: str, target: str) -> List[str]:
        """
        Translate a list of strings. Default: one-by-one.
        Override for providers that support native batching.
        """
        return [
            self.translate(t, source, target) if t.strip() else t
            for t in texts
        ]

    @abstractmethod
    def is_available(self) -> Tuple[bool, str]:
        """
        Check whether this provider is ready to use.
        Returns (available: bool, message: str).
        """
