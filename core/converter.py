"""
File conversion: DOCX ↔ PDF, batch support.
"""

from __future__ import annotations

import os
import subprocess
import shutil
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from utils.file_utils import build_output_path, unique_path
from utils.logger import get_logger

logger = get_logger("converter")

ProgressCB = Optional[Callable[[int], None]]
StatusCB = Optional[Callable[[str], None]]


# ---------------------------------------------------------------------------
# DOCX → PDF
# ---------------------------------------------------------------------------

def docx_to_pdf(
    input_path: str,
    output_path: Optional[str] = None,
    progress_callback: ProgressCB = None,
    status_callback: StatusCB = None,
    **_,
) -> str:
    """
    Convert a DOCX file to PDF.

    Strategy (in order):
      1. docx2pdf  (uses Microsoft Word on Windows – best formatting fidelity)
      2. LibreOffice headless

    Returns the output PDF path.
    """
    if output_path is None:
        output_path = build_output_path(input_path, None, ".pdf")
    output_path = unique_path(output_path)

    if status_callback:
        status_callback(f"Converting {Path(input_path).name} → PDF…")

    # Try docx2pdf first
    try:
        from docx2pdf import convert
        convert(input_path, output_path)
        if os.path.isfile(output_path):
            if progress_callback:
                progress_callback(100)
            logger.info("docx_to_pdf (docx2pdf) -> %s", output_path)
            return output_path
    except Exception as exc:
        logger.warning("docx2pdf failed (%s), trying LibreOffice…", exc)

    # Fall back to LibreOffice
    output_path = _lo_convert(input_path, str(Path(output_path).parent), "pdf")
    if progress_callback:
        progress_callback(100)
    logger.info("docx_to_pdf (LibreOffice) -> %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# PDF → DOCX
# ---------------------------------------------------------------------------

def pdf_to_docx(
    input_path: str,
    output_path: Optional[str] = None,
    progress_callback: ProgressCB = None,
    status_callback: StatusCB = None,
    **_,
) -> str:
    """
    Convert a PDF file to DOCX using pdf2docx.
    """
    if output_path is None:
        output_path = build_output_path(input_path, None, ".docx")
    output_path = unique_path(output_path)

    if status_callback:
        status_callback(f"Converting {Path(input_path).name} → DOCX…")

    try:
        from pdf2docx import Converter
        cv = Converter(input_path)
        cv.convert(output_path, multi_processing=False)
        cv.close()
    except Exception as exc:
        raise RuntimeError(f"pdf2docx conversion failed: {exc}") from exc

    if progress_callback:
        progress_callback(100)
    logger.info("pdf_to_docx -> %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# Batch conversion
# ---------------------------------------------------------------------------

def batch_convert(
    file_paths: List[str],
    conversion_type: str,
    output_dir: Optional[str] = None,
    progress_callback: ProgressCB = None,
    status_callback: StatusCB = None,
    **_,
) -> List[Tuple[str, Optional[str], Optional[str]]]:
    """
    Convert a list of files.

    Parameters
    ----------
    conversion_type : "docx_to_pdf" | "pdf_to_docx"
    output_dir      : destination directory (None = same as source)

    Returns a list of ``(input_path, output_path, error_message)`` tuples.
    """
    results: List[Tuple[str, Optional[str], Optional[str]]] = []
    total = len(file_paths)

    for idx, file_path in enumerate(file_paths):
        if status_callback:
            status_callback(f"Processing {Path(file_path).name} ({idx + 1}/{total})…")

        try:
            if conversion_type == "docx_to_pdf":
                out = build_output_path(file_path, output_dir, ".pdf")
                result = docx_to_pdf(file_path, out)
            elif conversion_type == "pdf_to_docx":
                out = build_output_path(file_path, output_dir, ".docx")
                result = pdf_to_docx(file_path, out)
            else:
                raise ValueError(f"Unknown conversion type: {conversion_type}")
            results.append((file_path, result, None))
        except Exception as exc:
            logger.error("Batch convert error for %s: %s", file_path, exc)
            results.append((file_path, None, str(exc)))

        if progress_callback:
            progress_callback(int((idx + 1) / total * 100))

    return results


# ---------------------------------------------------------------------------
# LibreOffice helper
# ---------------------------------------------------------------------------

def _lo_convert(input_path: str, output_dir: str, target_fmt: str) -> str:
    import config
    lo_exe = None
    for p in config.LIBREOFFICE_PATHS:
        if os.path.isfile(p):
            lo_exe = p
            break
    if lo_exe is None and shutil.which("soffice"):
        lo_exe = "soffice"
    if lo_exe is None:
        raise RuntimeError(
            "Neither docx2pdf nor LibreOffice is available for conversion. "
            "Please install LibreOffice."
        )

    stem = Path(input_path).stem
    expected_out = os.path.join(output_dir, f"{stem}.{target_fmt}")

    cmd = [
        lo_exe, "--headless",
        "--convert-to", target_fmt,
        "--outdir", output_dir,
        input_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"LibreOffice error:\n{result.stderr}")
    if not os.path.isfile(expected_out):
        raise RuntimeError("LibreOffice did not produce the expected output file.")
    return expected_out
