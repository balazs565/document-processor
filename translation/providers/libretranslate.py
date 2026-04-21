"""
LibreTranslate provider.

Works with:
  - The public API at https://libretranslate.com  (API key required)
  - A self-hosted instance at http://localhost:5000  (no key needed)

Language codes used: "en", "ro", "hu", "auto"
"""
from __future__ import annotations

from typing import List, Tuple

import requests

from translation.providers.base import TranslationProvider
from utils.logger import get_logger

logger = get_logger("libretranslate")


class LibreTranslateProvider(TranslationProvider):
    """HTTP client for LibreTranslate-compatible endpoints."""

    name = "LibreTranslate"

    def __init__(self, url: str = "http://localhost:5000", api_key: str = "") -> None:
        self._url = url.rstrip("/")
        self._api_key = api_key

    # ------------------------------------------------------------------
    # Availability check
    # ------------------------------------------------------------------

    def is_available(self) -> Tuple[bool, str]:
        try:
            resp = requests.get(f"{self._url}/languages", timeout=6)
            if resp.status_code == 200:
                return True, "Connected"
            return False, f"HTTP {resp.status_code}"
        except requests.exceptions.ConnectionError:
            return False, "Cannot connect – is the server running?"
        except Exception as exc:
            return False, str(exc)

    # ------------------------------------------------------------------
    # Translation
    # ------------------------------------------------------------------

    def translate(self, text: str, source: str, target: str) -> str:
        if not text.strip():
            return text

        payload: dict = {
            "q": text,
            "source": source,   # "auto" is supported
            "target": target,
            "format": "text",
        }
        if self._api_key:
            payload["api_key"] = self._api_key

        try:
            resp = requests.post(
                f"{self._url}/translate",
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json().get("translatedText", text)
        except requests.exceptions.HTTPError as exc:
            # Surface the API error message if present
            try:
                msg = exc.response.json().get("error", str(exc))
            except Exception:
                msg = str(exc)
            raise RuntimeError(f"LibreTranslate error: {msg}") from exc
        except requests.exceptions.Timeout:
            raise RuntimeError("LibreTranslate request timed out.")
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                "Cannot reach LibreTranslate. "
                "Start a local instance or configure a valid URL + API key."
            )

    def translate_batch(self, texts: List[str], source: str, target: str) -> List[str]:
        """Translate a list one-by-one (LibreTranslate has no native batch endpoint)."""
        return [
            self.translate(t, source, target) if t.strip() else t
            for t in texts
        ]
