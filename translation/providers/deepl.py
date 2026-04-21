"""
DeepL provider.

Requires a DeepL API key (free or pro).
Sign up at: https://www.deepl.com/pro-api

Install the optional dependency:
    pip install deepl

Language codes used internally: "en", "ro", "hu"
DeepL target codes:  "EN-US", "RO", "HU"
DeepL source codes:  "EN",    "RO", "HU"  (or None for auto-detect)
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from translation.providers.base import TranslationProvider
from utils.logger import get_logger

logger = get_logger("deepl_provider")

# Internal → DeepL mapping
_SOURCE_MAP = {"en": "EN", "ro": "RO", "hu": "HU", "auto": None}
_TARGET_MAP = {"en": "EN-US", "ro": "RO", "hu": "HU"}


class DeepLProvider(TranslationProvider):
    """Translation via the official DeepL Python SDK."""

    name = "DeepL"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._translator = None

    # ------------------------------------------------------------------
    # Lazy init
    # ------------------------------------------------------------------

    def _get_client(self):
        if self._translator is not None:
            return self._translator
        try:
            import deepl  # type: ignore
        except ImportError:
            raise RuntimeError(
                "The 'deepl' package is not installed.\n"
                "Run:  pip install deepl"
            )
        self._translator = deepl.Translator(self._api_key)
        return self._translator

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def is_available(self) -> Tuple[bool, str]:
        if not self._api_key:
            return False, "No DeepL API key configured."
        try:
            client = self._get_client()
            usage = client.get_usage()
            remaining = usage.character.limit - usage.character.count
            return True, f"Connected · {remaining:,} chars remaining"
        except RuntimeError as exc:
            return False, str(exc)
        except Exception as exc:
            return False, f"DeepL error: {exc}"

    # ------------------------------------------------------------------
    # Translation
    # ------------------------------------------------------------------

    def translate(self, text: str, source: str, target: str) -> str:
        if not text.strip():
            return text

        client = self._get_client()
        src = _SOURCE_MAP.get(source)           # None = DeepL auto-detect
        tgt = _TARGET_MAP.get(target)
        if tgt is None:
            raise ValueError(f"Unsupported DeepL target language: {target!r}")

        result = client.translate_text(text, source_lang=src, target_lang=tgt)
        return result.text

    def translate_batch(self, texts: List[str], source: str, target: str) -> List[str]:
        """DeepL supports up to 50 strings per request – use that for speed."""
        non_empty = [(i, t) for i, t in enumerate(texts) if t.strip()]
        if not non_empty:
            return texts

        client = self._get_client()
        src = _SOURCE_MAP.get(source)
        tgt = _TARGET_MAP.get(target)
        if tgt is None:
            raise ValueError(f"Unsupported DeepL target language: {target!r}")

        indices, chunks = zip(*non_empty)
        results = client.translate_text(list(chunks), source_lang=src, target_lang=tgt)

        output = list(texts)
        for i, result in zip(indices, results):
            output[i] = result.text
        return output
