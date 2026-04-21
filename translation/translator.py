"""
Main translation interface.

Usage
-----
    from translation.translator import Translator

    t = Translator(provider="libretranslate")
    translated = t.translate_text(
        "Hello world",
        source="en",
        target="ro",
        progress_callback=lambda p: ...,
        status_callback=lambda s: ...,
    )

Supported providers: "libretranslate", "deepl", "marianmt"
"""
from __future__ import annotations

import re
from typing import Callable, List, Optional, Tuple

import config
from translation.providers.base import TranslationProvider
from utils.logger import get_logger

logger = get_logger("translator")

ProgressCB = Optional[Callable[[int], None]]
StatusCB   = Optional[Callable[[str], None]]

# Default chunk size (characters) per API call
_DEFAULT_CHUNK  = 2000
_MARIAN_CHUNK   = 400     # MarianMT has smaller token limits


def _make_provider(name: str) -> TranslationProvider:
    if name == "libretranslate":
        from translation.providers.libretranslate import LibreTranslateProvider
        return LibreTranslateProvider(
            url=config.LIBRETRANSLATE_URL,
            api_key=config.LIBRETRANSLATE_API_KEY,
        )
    if name == "deepl":
        from translation.providers.deepl import DeepLProvider
        return DeepLProvider(api_key=config.DEEPL_API_KEY)
    if name == "marianmt":
        from translation.providers.marianmt import MarianMTProvider
        return MarianMTProvider()
    raise ValueError(f"Unknown translation provider: {name!r}")


class Translator:
    """
    High-level translation façade.

    Splits large texts into chunks, dispatches to the chosen provider,
    and reports progress through optional callbacks.
    """

    def __init__(self, provider: str = config.TRANSLATION_PROVIDER) -> None:
        self._provider_name = provider
        self._provider: Optional[TranslationProvider] = None

    # ------------------------------------------------------------------
    # Provider access (lazy)
    # ------------------------------------------------------------------

    @property
    def provider(self) -> TranslationProvider:
        if self._provider is None:
            self._provider = _make_provider(self._provider_name)
        return self._provider

    def check_availability(self) -> Tuple[bool, str]:
        """Return (available, message) for the current provider."""
        try:
            return self.provider.is_available()
        except Exception as exc:
            return False, str(exc)

    def switch_provider(self, name: str) -> None:
        self._provider_name = name
        self._provider = None      # reset lazy instance

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def translate_text(
        self,
        text: str,
        source: str,
        target: str,
        progress_callback: ProgressCB = None,
        status_callback:   StatusCB   = None,
    ) -> str:
        """
        Translate *text* (possibly large) from *source* to *target*.
        Splits into chunks internally and reassembles.
        """
        if not text.strip():
            return text

        chunk_size = (
            _MARIAN_CHUNK if self._provider_name == "marianmt" else _DEFAULT_CHUNK
        )
        chunks = _split_into_chunks(text, chunk_size)
        total  = len(chunks)
        translated_chunks: List[str] = []

        for i, chunk in enumerate(chunks):
            if status_callback:
                status_callback(f"Translating chunk {i + 1}/{total}…")
            translated_chunks.append(
                self.provider.translate(chunk, source, target)
            )
            if progress_callback:
                progress_callback(int((i + 1) / total * 100))

        return "".join(translated_chunks)

    def translate_paragraphs(
        self,
        paragraphs: List[str],
        source: str,
        target: str,
        progress_callback: ProgressCB = None,
        status_callback:   StatusCB   = None,
    ) -> List[str]:
        """
        Translate a list of paragraph strings.
        Each paragraph is translated individually to preserve structure.
        Empty paragraphs are passed through unchanged.
        """
        total   = len(paragraphs)
        results = []

        for i, para in enumerate(paragraphs):
            if status_callback:
                status_callback(f"Translating paragraph {i + 1}/{total}…")

            if para.strip():
                # If a single paragraph exceeds chunk size, split it further
                chunk_size = (
                    _MARIAN_CHUNK if self._provider_name == "marianmt"
                    else _DEFAULT_CHUNK
                )
                if len(para) > chunk_size:
                    chunks     = _split_into_chunks(para, chunk_size)
                    translated = "".join(
                        self.provider.translate(c, source, target) for c in chunks
                    )
                else:
                    translated = self.provider.translate(para, source, target)
                results.append(translated)
            else:
                results.append(para)   # preserve blank lines

            if progress_callback:
                progress_callback(int((i + 1) / total * 100))

        return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _split_into_chunks(text: str, max_chars: int) -> List[str]:
    """
    Split *text* into chunks of at most *max_chars* characters,
    preferring sentence boundaries (. ! ?) over hard breaks.
    """
    if len(text) <= max_chars:
        return [text]

    # Split on sentence boundaries first
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks: List[str] = []
    current = ""

    for sent in sentences:
        if len(current) + len(sent) + 1 <= max_chars:
            current = (current + " " + sent).lstrip()
        else:
            if current:
                chunks.append(current)
            # If a single sentence is too long, hard-split it
            if len(sent) > max_chars:
                for j in range(0, len(sent), max_chars):
                    chunks.append(sent[j: j + max_chars])
                current = ""
            else:
                current = sent

    if current:
        chunks.append(current)

    return chunks or [text]
