"""
PDF In-Place Translator
=======================
Translates a PDF while keeping its original visual layout:
  - Images, backgrounds, drawings, and graphics are untouched.
  - Only text blocks are redacted and rewritten in the target language.
  - Font, size, and colour are preserved as closely as possible.

Usage
-----
    from core.pdf_inplace_translator import translate_pdf_keeping_layout
    from translation.translator import Translator

    t = Translator(provider="libretranslate")
    translate_pdf_keeping_layout("input.pdf", "output.pdf", t, target_lang="ro")
"""
from __future__ import annotations

import re
from typing import Callable, List, Optional, Tuple

import fitz  # PyMuPDF

from translation.translator import Translator
from utils.logger import get_logger

logger = get_logger("pdf_inplace_translator")

ProgressCB = Optional[Callable[[int], None]]
StatusCB   = Optional[Callable[[str], None]]

# Minimum font size we'll attempt before giving up on fitting text.
_MIN_FONTSIZE = 5.0

# Base-14 PDF fonts – available in every PDF viewer without embedding.
_BASE14 = {
    "serif":        "Times-Roman",
    "serif-bold":   "Times-Bold",
    "serif-italic": "Times-Italic",
    "serif-bi":     "Times-BoldItalic",
    "sans":         "Helvetica",
    "sans-bold":    "Helvetica-Bold",
    "sans-italic":  "Helvetica-Oblique",
    "sans-bi":      "Helvetica-BoldOblique",
    "mono":         "Courier",
    "mono-bold":    "Courier-Bold",
    "mono-italic":  "Courier-Oblique",
    "mono-bi":      "Courier-BoldOblique",
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def translate_pdf_keeping_layout(
    input_path: str,
    output_path: str,
    translator: Translator,
    source_lang: str = "auto",
    target_lang: str = "ro",
    bg_color: Tuple[float, float, float] = (1.0, 1.0, 1.0),
    progress_callback: ProgressCB = None,
    status_callback:   StatusCB   = None,
) -> str:
    """
    Translate *input_path* in-place and save result to *output_path*.

    Parameters
    ----------
    input_path   : Source PDF path.
    output_path  : Destination PDF path.
    translator   : Configured ``Translator`` instance.
    source_lang  : Source language code or "auto".
    target_lang  : Target language code.
    bg_color     : RGB float tuple (0-1) for redaction fill behind new text.
                   Use ``None`` to let PyMuPDF use the original background.
    progress_callback : Called with 0-100 int values.
    status_callback   : Called with string log messages.

    Returns the *output_path*.
    """
    _log(status_callback, "Opening PDF…")

    with fitz.open(input_path) as doc:
        total = doc.page_count

        for page_num in range(total):
            page = doc[page_num]
            _log(status_callback, f"Processing page {page_num + 1}/{total}…")

            # 1. Extract text blocks
            blocks = _extract_blocks(page)
            if not blocks:
                _progress(progress_callback, int((page_num + 1) / total * 90))
                continue

            # 2. Translate all texts on the page in one batch
            texts = [b["text"] for b in blocks]
            try:
                translated = translator.translate_paragraphs(
                    texts,
                    source=source_lang,
                    target=target_lang,
                )
            except Exception as exc:
                _log(status_callback, f"  Warning: translation failed on page {page_num+1}: {exc}")
                translated = texts  # fall back to original

            # 3. Redact original text (batch – single apply_redactions call per page)
            fill = bg_color  # None → transparent, tuple → solid colour
            for block in blocks:
                rect = fitz.Rect(block["bbox"])
                annot = page.add_redact_annot(rect, fill=fill)

            # images=0 means "do NOT erase images under the redaction area"
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

            # 4. Insert translated text
            for block, trans_text in zip(blocks, translated):
                _insert_text(page, block, trans_text, bg_color=bg_color)

            _progress(
                progress_callback,
                int((page_num + 1) / total * 90),
            )

        _log(status_callback, "Saving translated PDF…")
        doc.save(output_path, garbage=3, deflate=True, clean=True)

    _progress(progress_callback, 100)
    _log(status_callback, f"Saved → {output_path}")
    logger.info("translate_pdf_keeping_layout -> %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# Block extraction
# ---------------------------------------------------------------------------

def _extract_blocks(page: fitz.Page) -> List[dict]:
    """
    Return a list of text block dicts:
        {
          "bbox":    (x0, y0, x1, y1),
          "text":    "joined span text",
          "size":    float,          # dominant font size
          "font":    str,            # dominant font name
          "flags":   int,            # dominant font flags
          "color":   float or tuple, # dominant colour
          "align":   int,            # 0=left, 1=center, 2=right, 3=justify
        }

    Blocks whose text is fewer than 2 characters are skipped.
    Image blocks (type != 0) are skipped entirely.
    """
    raw = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
    result: List[dict] = []

    for block in raw.get("blocks", []):
        if block.get("type") != 0:       # type 1 = image
            continue

        all_spans: List[dict] = []
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if span.get("text", "").strip():
                    all_spans.append(span)

        if not all_spans:
            continue

        # Join all span texts with spaces; normalise whitespace.
        joined = " ".join(
            re.sub(r"\s+", " ", sp["text"].strip())
            for sp in all_spans
        ).strip()

        if len(joined) < 2:
            continue

        # Pick dominant style (by text length weight)
        dominant = max(all_spans, key=lambda sp: len(sp.get("text", "")))

        result.append({
            "bbox":  tuple(block["bbox"]),
            "text":  joined,
            "size":  dominant.get("size", 11.0),
            "font":  dominant.get("font", "Helvetica"),
            "flags": dominant.get("flags", 0),
            "color": dominant.get("color", 0),
            "align": block.get("alignment", 0),
        })

    return result


# ---------------------------------------------------------------------------
# Text insertion
# ---------------------------------------------------------------------------

def _insert_text(
    page: fitz.Page,
    block: dict,
    text: str,
    bg_color: Optional[Tuple[float, float, float]],
) -> None:
    """Insert *text* into *page* at the position described by *block*."""
    rect  = fitz.Rect(block["bbox"])
    color = _int_to_rgb(block["color"])
    font  = _map_font(block["font"], block["flags"])
    size  = float(block["size"])

    # Attempt insertion, reducing font size until it fits or hits the minimum.
    while size >= _MIN_FONTSIZE:
        rc = page.insert_textbox(
            rect,
            text,
            fontname=font,
            fontsize=size,
            color=color,
            align=block.get("align", 0),
            expandtabs=4,
        )
        if rc >= 0:   # rc >= 0 means text fitted
            break
        size -= 0.5   # overflow – try smaller

    # If still overflows at minimum size, insert clipped (best-effort).
    if size < _MIN_FONTSIZE:
        page.insert_textbox(
            rect,
            text,
            fontname=font,
            fontsize=_MIN_FONTSIZE,
            color=color,
            align=block.get("align", 0),
            expandtabs=4,
        )


# ---------------------------------------------------------------------------
# Font mapping
# ---------------------------------------------------------------------------

def _map_font(font_name: str, flags: int) -> str:
    """
    Map an arbitrary PDF font name + flags to the nearest Base-14 font.

    PyMuPDF flags bits:
        bit 0  – superscript
        bit 1  – italic
        bit 2  – serifed
        bit 3  – monospaced
        bit 4  – bold
    """
    name_lower = font_name.lower()

    is_mono  = bool(flags & (1 << 3)) or any(k in name_lower for k in ("cour", "mono", "consol", "fixe"))
    is_serif = bool(flags & (1 << 2)) or any(k in name_lower for k in ("times", "roman", "georgia", "garamond", "serif"))
    is_bold  = bool(flags & (1 << 4)) or any(k in name_lower for k in ("bold", "demi", "black", "heavy"))
    is_italic= bool(flags & (1 << 1)) or any(k in name_lower for k in ("italic", "oblique", "slant"))

    if is_mono:
        family = "mono"
    elif is_serif:
        family = "serif"
    else:
        family = "sans"

    if is_bold and is_italic:
        key = f"{family}-bi"
    elif is_bold:
        key = f"{family}-bold"
    elif is_italic:
        key = f"{family}-italic"
    else:
        key = family

    return _BASE14.get(key, "Helvetica")


# ---------------------------------------------------------------------------
# Colour conversion
# ---------------------------------------------------------------------------

def _int_to_rgb(color) -> Tuple[float, float, float]:
    """
    Convert a PyMuPDF colour value to an (r, g, b) float tuple.

    The ``color`` field from ``get_text("dict")`` is:
      - An int  (packed 0xRRGGBB) for solid colours.
      - A float (greyscale 0-1) in some versions.
      - A tuple already in some edge cases.
    Returns (0, 0, 0) – black – for unrecognised values.
    """
    if isinstance(color, (list, tuple)):
        if len(color) == 3:
            return tuple(float(c) for c in color)
        return (0.0, 0.0, 0.0)

    if isinstance(color, float):
        return (color, color, color)

    if isinstance(color, int):
        r = ((color >> 16) & 0xFF) / 255.0
        g = ((color >>  8) & 0xFF) / 255.0
        b = ( color        & 0xFF) / 255.0
        return (r, g, b)

    return (0.0, 0.0, 0.0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _progress(cb: ProgressCB, value: int) -> None:
    if cb:
        cb(int(value))


def _log(cb: StatusCB, msg: str) -> None:
    if cb:
        cb(msg)
    logger.debug(msg)
