"""
MarianMT offline provider via HuggingFace Transformers.

Models are downloaded once and cached in ~/.docprocessor/models/.
No internet connection required after first use.

Install optional heavy dependencies:
    pip install transformers sentencepiece torch

Supported direct pairs:
    en → ro   Helsinki-NLP/opus-mt-en-ro
    ro → en   Helsinki-NLP/opus-mt-ro-en
    en → hu   Helsinki-NLP/opus-mt-en-hu
    hu → en   Helsinki-NLP/opus-mt-hu-en

Cross pairs (via English pivot):
    ro → hu   ro→en→hu
    hu → ro   hu→en→ro
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import config
from translation.providers.base import TranslationProvider
from utils.logger import get_logger

logger = get_logger("marianmt")

# Model map: (source, target) → HuggingFace model ID
_MODELS: Dict[Tuple[str, str], str] = {
    ("en", "ro"): "Helsinki-NLP/opus-mt-en-ro",
    ("ro", "en"): "Helsinki-NLP/opus-mt-ro-en",
    ("en", "hu"): "Helsinki-NLP/opus-mt-en-hu",
    ("hu", "en"): "Helsinki-NLP/opus-mt-hu-en",
}

# Pairs that need English as a pivot
_PIVOT_PAIRS = {
    ("ro", "hu"): ("ro", "en", "hu"),
    ("hu", "ro"): ("hu", "en", "ro"),
}

_MAX_INPUT_CHARS = 450   # safe limit per chunk for MarianMT tokeniser


class MarianMTProvider(TranslationProvider):
    """Offline translation using Helsinki-NLP MarianMT models."""

    name = "Offline (MarianMT)"

    def __init__(self, cache_dir: Optional[str] = None) -> None:
        self._cache_dir = cache_dir or os.path.join(config.CONFIG_DIR, "models")
        self._pipelines: Dict[Tuple[str, str], object] = {}
        os.makedirs(self._cache_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def is_available(self) -> Tuple[bool, str]:
        try:
            import transformers  # type: ignore  # noqa: F401
            import sentencepiece  # type: ignore  # noqa: F401
            return True, "transformers + sentencepiece available (models download on first use)"
        except ImportError as exc:
            return False, (
                f"Missing dependency: {exc.name}\n"
                "Run:  pip install transformers sentencepiece torch"
            )

    # ------------------------------------------------------------------
    # Pipeline factory
    # ------------------------------------------------------------------

    def _get_pipeline(self, source: str, target: str):
        key = (source, target)
        if key in self._pipelines:
            return self._pipelines[key]

        model_id = _MODELS.get(key)
        if model_id is None:
            raise ValueError(
                f"No direct MarianMT model for {source}→{target}. "
                "Use a different provider or enable pivot translation."
            )

        try:
            from transformers import MarianMTModel, MarianTokenizer  # type: ignore
        except ImportError:
            raise RuntimeError(
                "transformers is not installed.\n"
                "Run:  pip install transformers sentencepiece torch"
            )

        logger.info("Loading MarianMT model %s (this may take a moment)…", model_id)
        local_dir = os.path.join(self._cache_dir, model_id.replace("/", "_"))

        tokenizer = MarianTokenizer.from_pretrained(model_id, cache_dir=local_dir)
        model     = MarianMTModel.from_pretrained(model_id, cache_dir=local_dir)
        self._pipelines[key] = (tokenizer, model)
        logger.info("Model loaded: %s", model_id)
        return self._pipelines[key]

    # ------------------------------------------------------------------
    # Core translation
    # ------------------------------------------------------------------

    def _translate_direct(self, text: str, source: str, target: str) -> str:
        """Translate *text* using a loaded MarianMT pipeline."""
        tokenizer, model = self._get_pipeline(source, target)
        import torch  # type: ignore

        tokens = tokenizer([text], return_tensors="pt", padding=True, truncation=True, max_length=512)
        with torch.no_grad():
            translated = model.generate(**tokens)
        return tokenizer.decode(translated[0], skip_special_tokens=True)

    def translate(self, text: str, source: str, target: str) -> str:
        if not text.strip():
            return text

        # Resolve "auto" – try to detect language
        if source == "auto":
            source = self._detect_lang(text)

        # Handle pivot pairs
        if (source, target) in _PIVOT_PAIRS:
            src, pivot, tgt = _PIVOT_PAIRS[(source, target)]
            intermediate = self._translate_direct(text, src, pivot)
            return self._translate_direct(intermediate, pivot, tgt)

        return self._translate_direct(text, source, target)

    def translate_batch(self, texts: List[str], source: str, target: str) -> List[str]:
        return [self.translate(t, source, target) if t.strip() else t for t in texts]

    # ------------------------------------------------------------------
    # Language detection (simple heuristic, no extra lib needed)
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_lang(text: str) -> str:
        """
        Rough language detection based on characteristic Unicode characters.
        Falls back to "en".
        """
        sample = text[:300]
        ro_chars = set("ăâîșțĂÂÎȘȚ")
        hu_chars = set("áéíóöőúüűÁÉÍÓÖŐÚÜŰ")
        ro_score = sum(1 for c in sample if c in ro_chars)
        hu_score = sum(1 for c in sample if c in hu_chars)
        if ro_score > hu_score and ro_score > 2:
            return "ro"
        if hu_score > ro_score and hu_score > 2:
            return "hu"
        return "en"
