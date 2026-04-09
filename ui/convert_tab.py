"""
File conversion tab – DOCX ↔ PDF, batch support.
Layout is scroll-wrapped so adding files never collapses the options.
"""
from __future__ import annotations

import os
from typing import List

from PyQt6.QtCore import Qt, QThreadPool
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
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
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(18)

        # Heading
        layout.addWidget(QLabel("File Conversion", objectName="titleLabel"))
        layout.addWidget(QLabel(
            "Convert between Word (.docx) and PDF. Supports batch processing.",
            objectName="subtitleLabel"
        ))

        # Direction
        dir_group = QGroupBox("Conversion Direction")
        dir_layout = QHBoxLayout(dir_group)
        dir_layout.setSpacing(24)
        self._docx_to_pdf = QRadioButton("Word (.docx)  →  PDF")
        self._pdf_to_docx = QRadioButton("PDF  →  Word (.docx)")
        self._docx_to_pdf.setChecked(True)
        self._docx_to_pdf.toggled.connect(self._on_direction_changed)
        btn_grp = QButtonGroup(self)
        btn_grp.addButton(self._docx_to_pdf)
        btn_grp.addButton(self._pdf_to_docx)
        dir_layout.addWidget(self._docx_to_pdf)
        dir_layout.addWidget(self._pdf_to_docx)
        dir_layout.addStretch()
        layout.addWidget(dir_group)

        # Drop zone – fixed height prevents collapse
        self._drop_zone = DropZone(
            "Drop Word (.docx) files here",
            accepted_extensions=[".docx", ".doc"],
        )
        self._drop_zone.setFixedHeight(120)
        self._drop_zone.files_dropped.connect(self._add_files)
        layout.addWidget(self._drop_zone)

        # File list – constrained height
        files_group = QGroupBox("Files to Convert")
        fl = QVBoxLayout(files_group)
        self._file_list = FileListWidget(accepted_extensions=[".docx", ".doc"])
        self._file_list.setMinimumHeight(120)
        self._file_list.setMaximumHeight(220)
        fl.addWidget(self._file_list)
        add_btn = QPushButton("Add Files…")
        add_btn.clicked.connect(self._browse_files)
        fl.addWidget(add_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(files_group)

        # Output directory
        out_group = QGroupBox("Output")
        out_row = QHBoxLayout(out_group)
        self._out_label = QLabel("Same folder as source")
        self._out_label.setStyleSheet("color:#9aa0ac;")
        out_browse = QPushButton("Choose Folder…")
        out_browse.clicked.connect(self._browse_output)
        out_row.addWidget(QLabel("Save to:"))
        out_row.addWidget(self._out_label, 1)
        out_row.addWidget(out_browse)
        layout.addWidget(out_group)

        # Convert button
        self._convert_btn = QPushButton("Convert All")
        self._convert_btn.setObjectName("primaryButton")
        self._convert_btn.setFixedHeight(38)
        self._convert_btn.clicked.connect(self._run_conversion)
        layout.addWidget(self._convert_btn)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

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
        filt = ("Word Documents (*.docx *.doc);;All Files (*)"
                if self._docx_to_pdf.isChecked()
                else "PDF Files (*.pdf);;All Files (*)")
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
        worker = Worker(batch_convert, files, conv_type, self._output_dir)
        worker.signals.progress.connect(dlg.set_progress)
        worker.signals.status.connect(dlg.set_status)
        worker.signals.result.connect(self._on_done)
        worker.signals.error.connect(lambda e: (dlg.accept(), self._on_error(e)))
        worker.signals.finished.connect(dlg.accept)
        QThreadPool.globalInstance().start(worker)
        dlg.exec()

    def _on_done(self, results) -> None:
        ok  = [(i, o) for i, o, e in results if e is None]
        bad = [(i, e) for i, o, e in results if e is not None]
        msg = f"✓  {len(ok)} file(s) converted successfully."
        if bad:
            msg += f"\n\n✗  {len(bad)} failed:\n"
            msg += "\n".join(f"  • {os.path.basename(i)}: {e}" for i, e in bad)
        QMessageBox.information(self, "Done", msg)

    def _on_error(self, error_text: str) -> None:
        QMessageBox.critical(self, "Error", f"Conversion failed:\n\n{error_text}")

    def preload_files(self, paths: List[str]) -> None:
        from utils.file_utils import is_pdf, is_docx
        if any(is_pdf(p) for p in paths) and not any(is_docx(p) for p in paths):
            self._pdf_to_docx.setChecked(True)
        elif any(is_docx(p) for p in paths):
            self._docx_to_pdf.setChecked(True)
        self._add_files(paths)
