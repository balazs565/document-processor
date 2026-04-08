"""
OCR engine wrapper around Tesseract via pytesseract.

Supports Romanian (ron), Hungarian (hun), English (eng), and any other
language pack installed alongside Tesseract.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Callable, List, Optional

import fitz  # PyMuPDF
import pytesseract
from docx import Document
from PIL import Image

import config
from utils.file_utils import unique_path
from utils.logger import get_logger

logger = get_logger("ocr_engine")

ProgressCB = Optional[Callable[[int], None]]
StatusCB = Optional[Callable[[str], None]]


# ---------------------------------------------------------------------------
# Tesseract setup
# ---------------------------------------------------------------------------

def _configure_tesseract() -> bool:
    """Point pytesseract at the Tesseract binary; return True if found."""
    for path in config.TESSERACT_PATHS:
        if os.path.isfile(path):
            pytesseract.pytesseract.tesseract_cmd = path
            logger.debug("Tesseract found at: %s", path)
            return True
    # Check PATH
    import shutil
    if shutil.which("tesseract"):
        logger.debug("Tesseract found in PATH")
        return True
    logger.warning("Tesseract not found – OCR will fail.")
    return False


_TESSERACT_CONFIGURED = _configure_tesseract()


# ---------------------------------------------------------------------------
# Language utilities
# ---------------------------------------------------------------------------

def get_available_languages() -> List[str]:
    """Return list of installed Tesseract language codes."""
    try:
        langs = pytesseract.get_languages(config=r"--tessdata-dir")
        return [l for l in langs if l != "osd"]
    except Exception:
        return list(config.OCR_LANGUAGES.values())


def is_language_available(lang_code: str) -> bool:
    return lang_code in get_available_languages()


# ---------------------------------------------------------------------------
# OCR core
# ---------------------------------------------------------------------------

def perform_ocr(
    input_path: str,
    language: str = "eng",
    output_path: Optional[str] = None,
    dpi: int = 300,
    progress_callback: ProgressCB = None,
    status_callback: StatusCB = None,
    **_,
) -> str:
    """
    OCR a PDF (or image) and write the result to a DOCX file.

    Parameters
    ----------
    input_path  : Path to input PDF or image.
    language    : Tesseract language code (e.g. "ron", "hun", "ron+eng").
    output_path : Destination DOCX path. Auto-derived if None.
    dpi         : Resolution used when rendering PDF pages.

    Returns the output DOCX path.
    """
    if not _TESSERACT_CONFIGURED:
        raise RuntimeError(
            "Tesseract OCR is not installed or not found.\n"
            "Please install Tesseract and ensure it is in your PATH."
        )

    if output_path is None:
        output_path = unique_path(
            str(Path(input_path).with_suffix(".ocr.docx"))
        )

    ext = Path(input_path).suffix.lower()
    if ext == ".pdf":
        text_pages = _ocr_pdf(input_path, language, dpi, progress_callback, status_callback)
    elif ext in config.SUPPORTED_IMAGES:
        _status(status_callback, "Running OCR on image…")
        text = _ocr_image_file(input_path, language)
        text_pages = [text]
        _report(progress_callback, 100)
    else:
        raise ValueError(f"Unsupported file type for OCR: {ext}")

    _status(status_callback, "Writing DOCX…")
    _write_docx(text_pages, output_path)
    logger.info("perform_ocr -> %s (%d pages)", output_path, len(text_pages))
    return output_path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ocr_pdf(
    pdf_path: str,
    language: str,
    dpi: int,
    progress_callback: ProgressCB,
    status_callback: StatusCB,
) -> List[str]:
    """Render each PDF page and OCR it; return list of text strings."""
    text_pages: List[str] = []
    scale = dpi / 72.0
    mat = fitz.Matrix(scale, scale)

    with fitz.open(pdf_path) as doc:
        total = doc.page_count
        for i, page in enumerate(doc):
            _status(status_callback, f"OCR page {i + 1}/{total}…")
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

            # Enhance image for better OCR accuracy
            img = img.convert("L")  # greyscale

            text = pytesseract.image_to_string(img, lang=language)
            text_pages.append(text)
            _report(progress_callback, int((i + 1) / total * 100))

    return text_pages


def _ocr_image_file(image_path: str, language: str) -> str:
    img = Image.open(image_path).convert("L")
    return pytesseract.image_to_string(img, lang=language)


def _write_docx(text_pages: List[str], output_path: str) -> None:
    doc = Document()
    for page_num, text in enumerate(text_pages):
        if page_num > 0:
            doc.add_page_break()
        for line in text.split("\n"):
            doc.add_paragraph(line)
    doc.save(output_path)


def _report(cb: ProgressCB, value: int) -> None:
    if cb:
        cb(value)


def _status(cb: StatusCB, msg: str) -> None:
    if cb:
        cb(msg)
    logger.debug(msg)
