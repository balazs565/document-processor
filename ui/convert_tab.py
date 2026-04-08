"""
File conversion tab – DOCX ↔ PDF, with batch support.
"""

from __future__ import annotations

import os
from typing import List

from PyQt6.QtCore import Qt, QThreadPool
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from core.converter import batch_convert
from core.worker import Worker
from ui.widgets.drop_zone import DropZone
from ui.widgets.file_list import FileListWidget
from ui.widgets.progress_widget import ProgressDialog
from utils.recent_files import RecentFiles


class ConvertTab(QWidget):
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

        heading = QLabel("File Conversion")
        heading.setObjectName("titleLabel")
        sub = QLabel("Convert between Word (.docx) and PDF formats. Supports batch processing.")
        sub.setObjectName("subtitleLabel")
        layout.addWidget(heading)
        layout.addWidget(sub)

        # Conversion direction
        dir_group = QGroupBox("Conversion Direction")
        dir_layout = QHBoxLayout(dir_group)
        self._docx_to_pdf = QRadioButton("Word (.docx) → PDF")
        self._pdf_to_docx = QRadioButton("PDF → Word (.docx)")
        self._docx_to_pdf.setChecked(True)
        self._docx_to_pdf.toggled.connect(self._on_direction_changed)

        btn_group = QButtonGroup(self)
        btn_group.addButton(self._docx_to_pdf)
        btn_group.addButton(self._pdf_to_docx)

        dir_layout.addWidget(self._docx_to_pdf)
        dir_layout.addWidget(self._pdf_to_docx)
        dir_layout.addStretch()
        layout.addWidget(dir_group)

        # Drop zone
        self._drop_zone = DropZone(
            "Drop Word (.docx) files here",
            accepted_extensions=[".docx", ".doc"],
        )
        self._drop_zone.files_dropped.connect(self._add_files)
        layout.addWidget(self._drop_zone)

        # File list
        files_group = QGroupBox("Files to Convert")
        files_layout = QVBoxLayout(files_group)
        self._file_list = FileListWidget(accepted_extensions=[".docx", ".doc"])
        files_layout.addWidget(self._file_list)

        add_btn = QPushButton("Add Files…")
        add_btn.clicked.connect(self._browse_files)
        files_layout.addWidget(add_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(files_group)

        # Output directory
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

        # Convert button
        self._convert_btn = QPushButton("Convert All")
        self._convert_btn.setObjectName("primaryButton")
        self._convert_btn.setFixedHeight(40)
        self._convert_btn.clicked.connect(self._run_conversion)
        layout.addWidget(self._convert_btn)

        layout.addStretch()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_direction_changed(self) -> None:
        if self._docx_to_pdf.isChecked():
            self._drop_zone.set_label("Drop Word (.docx) files here")
            self._file_list._accepted = [".docx", ".doc"]
        else:
            self._drop_zone.set_label("Drop PDF files here")
            self._file_list._accepted = [".pdf"]
        self._file_list.clear_files()

    def _add_files(self, paths: List[str]) -> None:
        self._file_list.add_files(paths)
        for p in paths:
            self._recent.add(p)

    def _browse_files(self) -> None:
        if self._docx_to_pdf.isChecked():
            filt = "Word Documents (*.docx *.doc);;All Files (*)"
        else:
            filt = "PDF Files (*.pdf);;All Files (*)"
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Files", "", filt)
        if paths:
            self._add_files(paths)

    def _browse_output(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if d:
            self._output_dir = d
            self._out_label.setText(d)

    def _run_conversion(self) -> None:
        files = self._file_list.get_files()
        if not files:
            QMessageBox.warning(self, "No Files", "Please add files to convert.")
            return

        conv_type = "docx_to_pdf" if self._docx_to_pdf.isChecked() else "pdf_to_docx"

        dlg = ProgressDialog("Converting Files…", parent=self)

        worker = Worker(
            batch_convert,
            files,
            conv_type,
            self._output_dir,
        )
        worker.signals.progress.connect(dlg.set_progress)
        worker.signals.status.connect(dlg.set_status)
        worker.signals.result.connect(self._on_done)
        worker.signals.error.connect(self._on_error)
        worker.signals.finished.connect(dlg.accept)

        QThreadPool.globalInstance().start(worker)
        dlg.exec()

    def _on_done(self, results) -> None:
        successes = [(i, o) for i, o, e in results if e is None]
        failures = [(i, e) for i, o, e in results if e is not None]
        msg = f"Converted {len(successes)} file(s) successfully."
        if failures:
            msg += f"\n\n{len(failures)} file(s) failed:\n"
            msg += "\n".join(f"• {os.path.basename(i)}: {e}" for i, e in failures)
        QMessageBox.information(self, "Done", msg)

    def _on_error(self, error_text: str) -> None:
        QMessageBox.critical(self, "Error", f"Conversion failed:\n\n{error_text}")

    # ------------------------------------------------------------------
    # External API (called by main window after navigation)
    # ------------------------------------------------------------------

    def preload_files(self, paths: List[str]) -> None:
        """Pre-load files into the list (e.g. after drag-drop from home tab)."""
        from utils.file_utils import is_pdf, is_docx
        has_pdf = any(is_pdf(p) for p in paths)
        has_docx = any(is_docx(p) for p in paths)

        if has_pdf and not has_docx:
            self._pdf_to_docx.setChecked(True)
        elif has_docx and not has_pdf:
            self._docx_to_pdf.setChecked(True)

        self._add_files(paths)
