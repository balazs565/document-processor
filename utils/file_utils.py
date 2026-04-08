"""Filesystem helper utilities."""
import os
import shutil
from pathlib import Path
from typing import List, Optional

import config
from utils.logger import get_logger

logger = get_logger("file_utils")


def get_extension(file_path: str) -> str:
    return Path(file_path).suffix.lower()


def is_pdf(file_path: str) -> bool:
    return get_extension(file_path) in config.SUPPORTED_PDF


def is_docx(file_path: str) -> bool:
    return get_extension(file_path) in config.SUPPORTED_DOCX


def is_image(file_path: str) -> bool:
    return get_extension(file_path) in config.SUPPORTED_IMAGES


def detect_file_type(file_path: str) -> str:
    """Return 'pdf', 'docx', 'image', or 'unknown'."""
    if is_pdf(file_path):
        return "pdf"
    if is_docx(file_path):
        return "docx"
    if is_image(file_path):
        return "image"
    return "unknown"


def build_output_path(
    input_path: str,
    output_dir: Optional[str],
    new_ext: str,
    suffix: str = "",
) -> str:
    """Derive an output path from an input path with a new extension."""
    stem = Path(input_path).stem
    if suffix:
        stem = f"{stem}_{suffix}"
    filename = f"{stem}{new_ext}"
    base_dir = output_dir or str(Path(input_path).parent)
    return os.path.join(base_dir, filename)


def unique_path(file_path: str) -> str:
    """Append an incrementing counter to avoid overwriting an existing file."""
    if not os.path.exists(file_path):
        return file_path
    base = Path(file_path)
    counter = 1
    while True:
        candidate = base.parent / f"{base.stem}_{counter}{base.suffix}"
        if not os.path.exists(candidate):
            return str(candidate)
        counter += 1


def ensure_temp_dir() -> str:
    os.makedirs(config.TEMP_DIR, exist_ok=True)
    return config.TEMP_DIR


def clean_temp_dir() -> None:
    if os.path.exists(config.TEMP_DIR):
        shutil.rmtree(config.TEMP_DIR, ignore_errors=True)
    os.makedirs(config.TEMP_DIR, exist_ok=True)


def file_size_mb(file_path: str) -> float:
    return os.path.getsize(file_path) / (1024 * 1024)


def format_size(size_bytes: int) -> str:
    for unit, threshold in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
        if size_bytes >= threshold:
            return f"{size_bytes / threshold:.1f} {unit}"
    return f"{size_bytes} B"


def validate_files(paths: List[str]) -> List[str]:
    """Filter list to files that actually exist on disk."""
    valid = []
    for p in paths:
        if os.path.isfile(p):
            valid.append(p)
        else:
            logger.warning("File not found: %s", p)
    return valid
