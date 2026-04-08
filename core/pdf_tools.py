"""
All PDF manipulation operations.

Every public function follows the same contract:
  - Accepts optional ``progress_callback(int)`` and ``status_callback(str)``
    keyword arguments so it can be called both directly and from a Worker.
  - Returns a result value or raises an exception on failure.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import fitz  # PyMuPDF
from PIL import Image

import config
from utils.file_utils import unique_path, ensure_temp_dir
from utils.logger import get_logger

logger = get_logger("pdf_tools")

# Type aliases
ProgressCB = Optional[Callable[[int], None]]
StatusCB = Optional[Callable[[str], None]]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _open(path: str) -> fitz.Document:
    doc = fitz.open(path)
    return doc


def _report(progress_callback: ProgressCB, value: int) -> None:
    if progress_callback:
        progress_callback(value)


def _status(status_callback: StatusCB, msg: str) -> None:
    if status_callback:
        status_callback(msg)
    logger.debug(msg)


# ---------------------------------------------------------------------------
# Information
# ---------------------------------------------------------------------------

def get_page_count(input_path: str, **_) -> int:
    with _open(input_path) as doc:
        return doc.page_count


def is_scanned_pdf(input_path: str, sample_pages: int = 5, **_) -> bool:
    """
    Heuristic: a PDF is 'scanned' if sampled pages contain almost no selectable
    text but do contain large image objects.
    """
    with _open(input_path) as doc:
        pages_to_check = min(sample_pages, doc.page_count)
        text_chars = 0
        image_count = 0
        for i in range(pages_to_check):
            page = doc[i]
            text_chars += len(page.get_text("text").strip())
            image_count += len(page.get_images(full=False))
        avg_text = text_chars / max(pages_to_check, 1)
        scanned = avg_text < 50 and image_count > 0
        logger.debug(
            "is_scanned=%s (avg_text=%.1f, images=%d)", scanned, avg_text, image_count
        )
        return scanned


def get_page_thumbnails(
    input_path: str,
    width: int = config.THUMBNAIL_WIDTH,
    height: int = config.THUMBNAIL_HEIGHT,
    **_,
) -> List[bytes]:
    """Return a list of PNG bytes (one per page) for the page-arranger UI."""
    thumbnails: List[bytes] = []
    with _open(input_path) as doc:
        for page in doc:
            mat = fitz.Matrix(width / page.rect.width, height / page.rect.height)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            thumbnails.append(pix.tobytes("png"))
    return thumbnails


# ---------------------------------------------------------------------------
# Split
# ---------------------------------------------------------------------------

def split_pdf(
    input_path: str,
    output_dir: str,
    ranges: Optional[List[Tuple[int, int]]] = None,
    individual_pages: bool = False,
    progress_callback: ProgressCB = None,
    status_callback: StatusCB = None,
    **_,
) -> List[str]:
    """
    Split *input_path* into separate PDFs.

    Parameters
    ----------
    ranges:
        List of (start, end) 1-based inclusive page ranges.
        If None and individual_pages=False, each page becomes its own file.
    individual_pages:
        When True every page is exported individually (overrides *ranges*).
    """
    os.makedirs(output_dir, exist_ok=True)
    stem = Path(input_path).stem
    output_files: List[str] = []

    with _open(input_path) as doc:
        total = doc.page_count

        if individual_pages or ranges is None:
            # One file per page
            for i in range(total):
                _status(status_callback, f"Extracting page {i + 1}/{total}…")
                out_path = unique_path(os.path.join(output_dir, f"{stem}_page{i + 1}.pdf"))
                sub = fitz.open()
                sub.insert_pdf(doc, from_page=i, to_page=i)
                sub.save(out_path)
                sub.close()
                output_files.append(out_path)
                _report(progress_callback, int((i + 1) / total * 100))
        else:
            for idx, (start, end) in enumerate(ranges):
                s = max(0, start - 1)
                e = min(total - 1, end - 1)
                _status(status_callback, f"Extracting pages {start}-{end}…")
                out_path = unique_path(
                    os.path.join(output_dir, f"{stem}_p{start}-{end}.pdf")
                )
                sub = fitz.open()
                sub.insert_pdf(doc, from_page=s, to_page=e)
                sub.save(out_path)
                sub.close()
                output_files.append(out_path)
                _report(progress_callback, int((idx + 1) / len(ranges) * 100))

    logger.info("split_pdf -> %d files", len(output_files))
    return output_files


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------

def merge_pdfs(
    input_paths: List[str],
    output_path: str,
    progress_callback: ProgressCB = None,
    status_callback: StatusCB = None,
    **_,
) -> str:
    """Merge *input_paths* into a single PDF at *output_path*."""
    merged = fitz.open()
    total = len(input_paths)

    for idx, path in enumerate(input_paths):
        _status(status_callback, f"Merging {Path(path).name} ({idx + 1}/{total})…")
        with _open(path) as doc:
            merged.insert_pdf(doc)
        _report(progress_callback, int((idx + 1) / total * 100))

    merged.save(output_path)
    merged.close()
    logger.info("merge_pdfs -> %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# Compress
# ---------------------------------------------------------------------------

def compress_pdf(
    input_path: str,
    output_path: str,
    quality: int = config.DEFAULT_COMPRESSION_QUALITY,
    progress_callback: ProgressCB = None,
    status_callback: StatusCB = None,
    **_,
) -> str:
    """
    Re-render each page as a compressed JPEG image and rebuild the PDF.
    *quality* is 1-100 (JPEG quality).
    """
    quality = max(1, min(100, quality))
    _status(status_callback, "Compressing PDF…")

    with _open(input_path) as doc:
        out_doc = fitz.open()
        total = doc.page_count

        for i, page in enumerate(doc):
            _status(status_callback, f"Compressing page {i + 1}/{total}…")
            # Render at 150 dpi
            mat = fitz.Matrix(150 / 72, 150 / 72)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            # Convert pixmap -> Pillow -> JPEG bytes -> back into new PDF page
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            buf = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            buf_path = buf.name
            buf.close()
            img.save(buf_path, "JPEG", quality=quality, optimize=True)

            img_doc = fitz.open(buf_path)
            img_pdfbytes = img_doc.convert_to_pdf()
            img_doc.close()
            os.unlink(buf_path)

            img_pdf = fitz.open("pdf", img_pdfbytes)
            out_doc.insert_pdf(img_pdf)
            img_pdf.close()
            _report(progress_callback, int((i + 1) / total * 100))

        out_doc.save(output_path, deflate=True, garbage=4)
        out_doc.close()

    logger.info("compress_pdf quality=%d -> %s", quality, output_path)
    return output_path


# ---------------------------------------------------------------------------
# Extract images
# ---------------------------------------------------------------------------

def extract_images_from_pdf(
    input_path: str,
    output_dir: str,
    progress_callback: ProgressCB = None,
    status_callback: StatusCB = None,
    **_,
) -> List[str]:
    """Extract all embedded images from the PDF and save them to *output_dir*."""
    os.makedirs(output_dir, exist_ok=True)
    saved: List[str] = []

    with _open(input_path) as doc:
        total = doc.page_count
        for page_num, page in enumerate(doc):
            _status(status_callback, f"Scanning page {page_num + 1}/{total}…")
            for img_index, img_info in enumerate(page.get_images(full=True)):
                xref = img_info[0]
                base_image = doc.extract_image(xref)
                ext = base_image.get("ext", "png")
                image_bytes = base_image["image"]
                out_path = unique_path(
                    os.path.join(output_dir, f"img_p{page_num + 1}_{img_index + 1}.{ext}")
                )
                with open(out_path, "wb") as f:
                    f.write(image_bytes)
                saved.append(out_path)
            _report(progress_callback, int((page_num + 1) / total * 100))

    logger.info("extract_images -> %d images", len(saved))
    return saved


# ---------------------------------------------------------------------------
# Extract text
# ---------------------------------------------------------------------------

def extract_text_from_pdf(
    input_path: str,
    progress_callback: ProgressCB = None,
    status_callback: StatusCB = None,
    **_,
) -> str:
    """Return plain text extracted from all pages."""
    parts: List[str] = []
    with _open(input_path) as doc:
        total = doc.page_count
        for i, page in enumerate(doc):
            _status(status_callback, f"Extracting text page {i + 1}/{total}…")
            parts.append(page.get_text("text"))
            _report(progress_callback, int((i + 1) / total * 100))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Page manipulation
# ---------------------------------------------------------------------------

def rearrange_pages(
    input_path: str,
    output_path: str,
    page_order: List[int],
    progress_callback: ProgressCB = None,
    status_callback: StatusCB = None,
    **_,
) -> str:
    """
    Re-export pages in the order given by *page_order* (0-based indices).
    """
    _status(status_callback, "Rearranging pages…")
    with _open(input_path) as doc:
        out_doc = fitz.open()
        total = len(page_order)
        for idx, page_idx in enumerate(page_order):
            out_doc.insert_pdf(doc, from_page=page_idx, to_page=page_idx)
            _report(progress_callback, int((idx + 1) / total * 100))
        out_doc.save(output_path)
        out_doc.close()
    logger.info("rearrange_pages -> %s", output_path)
    return output_path


def delete_pages(
    input_path: str,
    output_path: str,
    pages_to_delete: List[int],
    progress_callback: ProgressCB = None,
    status_callback: StatusCB = None,
    **_,
) -> str:
    """
    Export the PDF without the pages listed in *pages_to_delete* (0-based).
    """
    _status(status_callback, "Deleting pages…")
    with _open(input_path) as doc:
        keep = [i for i in range(doc.page_count) if i not in pages_to_delete]
        out_doc = fitz.open()
        total = len(keep)
        for idx, page_idx in enumerate(keep):
            out_doc.insert_pdf(doc, from_page=page_idx, to_page=page_idx)
            _report(progress_callback, int((idx + 1) / total * 100))
        out_doc.save(output_path)
        out_doc.close()
    logger.info("delete_pages %s -> %s", pages_to_delete, output_path)
    return output_path


def rotate_pages(
    input_path: str,
    output_path: str,
    rotations: Dict[int, int],
    progress_callback: ProgressCB = None,
    status_callback: StatusCB = None,
    **_,
) -> str:
    """
    Rotate pages according to *rotations* dict {0-based page index: degrees}.
    Valid degrees: 0, 90, 180, 270.
    """
    _status(status_callback, "Rotating pages…")
    with _open(input_path) as doc:
        total = doc.page_count
        for i in range(total):
            if i in rotations:
                page = doc[i]
                page.set_rotation(rotations[i])
            _report(progress_callback, int((i + 1) / total * 100))
        doc.save(output_path)
    logger.info("rotate_pages -> %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# Watermark
# ---------------------------------------------------------------------------

def add_watermark(
    input_path: str,
    output_path: str,
    text: Optional[str] = None,
    image_path: Optional[str] = None,
    opacity: float = 0.3,
    font_size: int = 60,
    progress_callback: ProgressCB = None,
    status_callback: StatusCB = None,
    **_,
) -> str:
    """Add a text or image watermark to every page."""
    with _open(input_path) as doc:
        total = doc.page_count
        for i, page in enumerate(doc):
            _status(status_callback, f"Watermarking page {i + 1}/{total}…")
            rect = page.rect

            if text:
                # Draw diagonal text watermark
                wm_page = fitz.open()
                wm = wm_page.new_page(width=rect.width, height=rect.height)
                wm.insert_text(
                    fitz.Point(rect.width * 0.15, rect.height * 0.55),
                    text,
                    fontsize=font_size,
                    color=(0.7, 0.7, 0.7),
                    rotate=45,
                )
                page.show_pdf_page(rect, wm_page, 0, overlay=True, oc=0, keep_proportion=True)
                # Simpler approach: just insert text directly
                page.insert_text(
                    fitz.Point(rect.width * 0.15, rect.height * 0.55),
                    text,
                    fontsize=font_size,
                    color=(0.7, 0.7, 0.7),
                    rotate=45,
                )
                wm_page.close()

            if image_path and os.path.isfile(image_path):
                img_rect = fitz.Rect(
                    rect.width * 0.3,
                    rect.height * 0.35,
                    rect.width * 0.7,
                    rect.height * 0.65,
                )
                page.insert_image(img_rect, filename=image_path, overlay=True)

            _report(progress_callback, int((i + 1) / total * 100))

        doc.save(output_path)
    logger.info("add_watermark -> %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# Password protection
# ---------------------------------------------------------------------------

def add_password(
    input_path: str,
    output_path: str,
    password: str,
    progress_callback: ProgressCB = None,
    status_callback: StatusCB = None,
    **_,
) -> str:
    """Encrypt the PDF with *password* (user + owner password)."""
    _status(status_callback, "Adding password protection…")
    with _open(input_path) as doc:
        encrypt_meth = fitz.PDF_ENCRYPT_AES_256
        doc.save(
            output_path,
            encryption=encrypt_meth,
            user_pw=password,
            owner_pw=password,
        )
    _report(progress_callback, 100)
    logger.info("add_password -> %s", output_path)
    return output_path


def remove_password(
    input_path: str,
    output_path: str,
    password: str,
    progress_callback: ProgressCB = None,
    status_callback: StatusCB = None,
    **_,
) -> str:
    """Decrypt the PDF (requires knowing the current password)."""
    _status(status_callback, "Removing password…")
    doc = fitz.open(input_path)
    if doc.needs_pass:
        if not doc.authenticate(password):
            doc.close()
            raise ValueError("Incorrect password.")
    doc.save(output_path, encryption=fitz.PDF_ENCRYPT_NONE)
    doc.close()
    _report(progress_callback, 100)
    logger.info("remove_password -> %s", output_path)
    return output_path
