"""
OCR tab – extract text from scanned PDFs and images.
"""

from __future__ import annotations

import os
from typing import List

from PyQt6.QtCore import Qt, QThreadPool
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import config
from core.ocr_engine import perform_ocr
from core.worker import Worker
from ui.widgets.drop_zone import DropZone
from ui.widgets.file_list import FileListWidget
from ui.widgets.progress_widget import ProgressDialog
from utils.recent_files import RecentFiles


class OCRTab(QWidget):
    def __init__(self, recent_files: RecentFiles, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._recent = recent_files
        self._output_dir: str | None = None
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        heading = QLabel("OCR – Text Recognition")
        heading.setObjectName("titleLabel")
        sub = QLabel(
            "Extract text from scanned PDFs or images. "
            "Supports Romanian, Hungarian and more."
        )
        sub.setObjectName("subtitleLabel")
        sub.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(sub)

        # Language selection
        lang_group = QGroupBox("Language Settings")
        lang_layout = QVBoxLayout(lang_group)

        primary_row = QHBoxLayout()
        primary_row.addWidget(QLabel("Primary language:"))
        self._lang_combo = QComboBox()
        for display, code in config.OCR_LANGUAGES.items():
            self._lang_combo.addItem(display, code)
        # Default: Romanian
        self._lang_combo.setCurrentText("Romanian")
        primary_row.addWidget(self._lang_combo)
        primary_row.addStretch()

        secondary_row = QHBoxLayout()
        secondary_row.addWidget(QLabel("Also include English:"))
        self._eng_check = QCheckBox()
        self._eng_check.setChecked(False)
        secondary_row.addWidget(self._eng_check)
        secondary_row.addStretch()

        dpi_row = QHBoxLayout()
        dpi_row.addWidget(QLabel("Scan DPI (higher = better quality, slower):"))
        self._dpi_combo = QComboBox()
        for dpi in ["150", "200", "300", "400", "600"]:
            self._dpi_combo.addItem(f"{dpi} DPI", int(dpi))
        self._dpi_combo.setCurrentText("300 DPI")
        dpi_row.addWidget(self._dpi_combo)
        dpi_row.addStretch()

        lang_layout.addLayout(primary_row)
        lang_layout.addLayout(secondary_row)
        lang_layout.addLayout(dpi_row)
        layout.addWidget(lang_group)

        # Drop zone
        self._drop_zone = DropZone(
            "Drop PDF or image files here",
            accepted_extensions=[".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"],
        )
        self._drop_zone.files_dropped.connect(self._add_files)
        layout.addWidget(self._drop_zone)

        # File list
        files_group = QGroupBox("Files to OCR")
        files_layout = QVBoxLayout(files_group)
        self._file_list = FileListWidget(
            accepted_extensions=[".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"]
        )
        files_layout.addWidget(self._file_list)

        add_btn = QPushButton("Add Files…")
        add_btn.clicked.connect(self._browse_files)
        files_layout.addWidget(add_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(files_group)

        # Output
        out_group = QGroupBox("Output")
        out_layout = QHBoxLayout(out_group)
        self._out_label = QLabel("Same folder as source")
        self._out_label.setStyleSheet("color: #6c7086;")
        out_browse = QPushButton("Choose Folder…")
        out_browse.clicked.connect(self._browse_output)
        out_layout.addWidget(QLabel("Save to:"))
        out_layout.addWidget(self._out_label, 1)
        out_layout.addWidget(out_browse)
        layout.addWidget(out_group)

        # Run button
        self._run_btn = QPushButton("Run OCR")
        self._run_btn.setObjectName("primaryButton")
        self._run_btn.setFixedHeight(40)
        self._run_btn.clicked.connect(self._run_ocr)
        layout.addWidget(self._run_btn)

        # Note
        note = QLabel(
            "⚠️  Tesseract OCR must be installed with the ron and hun language packs.\n"
            "    See README for installation instructions."
        )
        note.setStyleSheet("color: #f9e2af; font-size: 11px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        layout.addStretch()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _add_files(self, paths: List[str]) -> None:
        self._file_list.add_files(paths)
        for p in paths:
            self._recent.add(p)

    def _browse_files(self) -> None:
        filt = "PDF & Images (*.pdf *.png *.jpg *.jpeg *.tiff *.bmp);;All Files (*)"
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Files", "", filt)
        if paths:
            self._add_files(paths)

    def _browse_output(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if d:
            self._output_dir = d
            self._out_label.setText(d)

    def _build_lang_string(self) -> str:
        lang = self._lang_combo.currentData()
        if self._eng_check.isChecked() and lang != "eng":
            return f"{lang}+eng"
        return lang

    def _run_ocr(self) -> None:
        files = self._file_list.get_files()
        if not files:
            QMessageBox.warning(self, "No Files", "Please add files to process.")
            return

        lang = self._build_lang_string()
        dpi = self._dpi_combo.currentData()

        successes: List[str] = []
        errors: List[str] = []

        dlg = ProgressDialog("Running OCR…", parent=self)

        def run_all(progress_callback, status_callback):
            total = len(files)
            for idx, file_path in enumerate(files):
                if self._output_dir:
                    stem = os.path.splitext(os.path.basename(file_path))[0]
                    out = os.path.join(self._output_dir, f"{stem}_ocr.docx")
                else:
                    out = None
                try:
                    status_callback(
                        f"OCR: {os.path.basename(file_path)} ({idx + 1}/{total})…"
                    )
                    result = perform_ocr(
                        file_path,
                        language=lang,
                        output_path=out,
                        dpi=dpi,
                        progress_callback=lambda p: progress_callback(
                            int(((idx + p / 100) / total) * 100)
                        ),
                        status_callback=status_callback,
                    )
                    successes.append(result)
                except Exception as exc:
                    errors.append(f"{os.path.basename(file_path)}: {exc}")
            return (successes, errors)

        worker = Worker(run_all)
        worker.signals.progress.connect(dlg.set_progress)
        worker.signals.status.connect(dlg.set_status)
        worker.signals.result.connect(lambda r: self._on_done(r[0], r[1]))
        worker.signals.error.connect(self._on_error)
        worker.signals.finished.connect(dlg.accept)

        QThreadPool.globalInstance().start(worker)
        dlg.exec()

    def _on_done(self, successes: List[str], errors: List[str]) -> None:
        msg = f"OCR completed for {len(successes)} file(s)."
        if errors:
            msg += f"\n\n{len(errors)} error(s):\n" + "\n".join(f"• {e}" for e in errors)
        QMessageBox.information(self, "Done", msg)

    def _on_error(self, error_text: str) -> None:
        QMessageBox.critical(self, "Error", f"OCR failed:\n\n{error_text}")

    # ------------------------------------------------------------------
    # External API
    # ------------------------------------------------------------------

    def preload_files(self, paths: List[str]) -> None:
        self._add_files(paths)
