"""
DOCX Tools tab – extract images, convert to images, and view document info.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

from PyQt6.QtCore import Qt, QThreadPool
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
)

from core.docx_tools import extract_images_from_docx, docx_to_images, get_docx_info
from core.worker import Worker
from ui.widgets.drop_zone import DropZone
from ui.widgets.progress_widget import ProgressDialog
from utils.file_utils import unique_path, build_output_path
from utils.recent_files import RecentFiles


class DocxToolsTab(QWidget):
    def __init__(self, recent_files: RecentFiles, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._recent = recent_files
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Left nav
        self._nav = QListWidget()
        self._nav.setFixedWidth(180)
        self._nav.setStyleSheet(
            "QListWidget { background: #181825; border: none; border-right: 1px solid #313244; }"
            "QListWidget::item { padding: 10px 14px; color: #a6adc8; }"
            "QListWidget::item:selected { background: #313244; color: #7c6af5; font-weight: bold; }"
            "QListWidget::item:hover:!selected { background: #252537; color: #cdd6f4; }"
        )
        tools = [
            ("🖼️  Extract Images", "extract_images"),
            ("📸  Convert to Images", "to_images"),
            ("ℹ️  Document Info", "info"),
        ]
        for label, key in tools:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self._nav.addItem(item)

        self._nav.currentRowChanged.connect(lambda row: self._stack.setCurrentIndex(row))

        # Stack
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_extract_images_panel())
        self._stack.addWidget(self._build_to_images_panel())
        self._stack.addWidget(self._build_info_panel())

        main_layout.addWidget(self._nav)
        main_layout.addWidget(self._stack)
        self._nav.setCurrentRow(0)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _single_file_picker(self, parent: QWidget) -> tuple:
        group = QGroupBox("Input DOCX File")
        gl = QHBoxLayout(group)
        line = QLineEdit()
        line.setReadOnly(True)
        line.setPlaceholderText("Select a Word document…")
        btn = QPushButton("Browse…")

        def browse():
            path, _ = QFileDialog.getOpenFileName(
                parent, "Select DOCX", "",
                "Word Documents (*.docx *.doc);;All Files (*)"
            )
            if path:
                line.setText(path)
                self._recent.add(path)

        btn.clicked.connect(browse)
        gl.addWidget(line, 1)
        gl.addWidget(btn)
        return group, lambda: line.text()

    def _output_dir_picker(self, parent: QWidget) -> tuple:
        group = QGroupBox("Output Folder")
        gl = QHBoxLayout(group)
        line = QLineEdit()
        line.setReadOnly(True)
        line.setPlaceholderText("Same folder as source (default)")
        btn = QPushButton("Choose…")

        def browse():
            d = QFileDialog.getExistingDirectory(parent, "Select Output Folder")
            if d:
                line.setText(d)

        btn.clicked.connect(browse)
        gl.addWidget(line, 1)
        gl.addWidget(btn)
        return group, lambda: line.text() or None

    def _run_worker(self, fn, *args, title="Processing…", on_result=None, **kwargs) -> None:
        dlg = ProgressDialog(title, parent=self)
        worker = Worker(fn, *args, **kwargs)
        worker.signals.progress.connect(dlg.set_progress)
        worker.signals.status.connect(dlg.set_status)

        if on_result:
            worker.signals.result.connect(on_result)
        else:
            worker.signals.result.connect(self._default_result)

        worker.signals.error.connect(lambda e: self._show_error(e, dlg))
        worker.signals.finished.connect(dlg.accept)
        QThreadPool.globalInstance().start(worker)
        dlg.exec()

    def _default_result(self, result) -> None:
        if isinstance(result, list):
            msg = f"Done! {len(result)} file(s) saved."
        else:
            msg = f"Done!\n{result}"
        QMessageBox.information(self, "Done", msg)

    def _show_error(self, error_text: str, dlg: ProgressDialog | None = None) -> None:
        if dlg:
            dlg.accept()
        QMessageBox.critical(self, "Error", f"Operation failed:\n\n{error_text}")

    # ------------------------------------------------------------------
    # Extract Images panel
    # ------------------------------------------------------------------

    def _build_extract_images_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        layout.addWidget(QLabel("Extract Images from DOCX", objectName="titleLabel"))
        layout.addWidget(QLabel(
            "Save all images embedded in a Word document.",
            objectName="subtitleLabel"
        ))

        in_group, self._ei_input = self._single_file_picker(w)
        layout.addWidget(in_group)

        out_group, self._ei_output = self._output_dir_picker(w)
        layout.addWidget(out_group)

        # Drop zone shortcut
        drop = DropZone(
            "Or drop a .docx file here",
            accepted_extensions=[".docx", ".doc"],
        )
        drop.files_dropped.connect(lambda paths: self._ei_quick(paths[0]))
        layout.addWidget(drop)

        btn = QPushButton("Extract Images")
        btn.setObjectName("primaryButton")
        btn.setFixedHeight(40)
        btn.clicked.connect(self._run_extract_images)
        layout.addWidget(btn)
        layout.addStretch()
        return w

    def _run_extract_images(self) -> None:
        path = self._ei_input()
        if not path:
            QMessageBox.warning(self, "No File", "Please select a DOCX file.")
            return
        out_dir = self._ei_output() or str(Path(path).parent)
        self._run_worker(
            extract_images_from_docx, path, out_dir, title="Extracting Images…"
        )

    def _ei_quick(self, path: str) -> None:
        out_dir = str(Path(path).parent)
        self._run_worker(
            extract_images_from_docx, path, out_dir, title="Extracting Images…"
        )

    # ------------------------------------------------------------------
    # Convert to Images panel
    # ------------------------------------------------------------------

    def _build_to_images_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        layout.addWidget(QLabel("Convert DOCX to Images", objectName="titleLabel"))
        layout.addWidget(QLabel(
            "Render each page of a Word document as a PNG image.\n"
            "Requires LibreOffice to be installed.",
            objectName="subtitleLabel"
        ))

        in_group, self._ti_input = self._single_file_picker(w)
        layout.addWidget(in_group)

        opts_group = QGroupBox("Options")
        ol = QHBoxLayout(opts_group)
        ol.addWidget(QLabel("Resolution (DPI):"))
        self._ti_dpi = QComboBox()
        for dpi in ["72", "96", "150", "200", "300"]:
            self._ti_dpi.addItem(f"{dpi} DPI", int(dpi))
        self._ti_dpi.setCurrentText("150 DPI")
        ol.addWidget(self._ti_dpi)
        ol.addStretch()
        layout.addWidget(opts_group)

        out_group, self._ti_output = self._output_dir_picker(w)
        layout.addWidget(out_group)

        btn = QPushButton("Convert to Images")
        btn.setObjectName("primaryButton")
        btn.setFixedHeight(40)
        btn.clicked.connect(self._run_to_images)
        layout.addWidget(btn)

        note = QLabel(
            "⚠️  LibreOffice must be installed for this feature to work.\n"
            "    See README for installation instructions."
        )
        note.setStyleSheet("color: #f9e2af; font-size: 11px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        layout.addStretch()
        return w

    def _run_to_images(self) -> None:
        path = self._ti_input()
        if not path:
            QMessageBox.warning(self, "No File", "Please select a DOCX file.")
            return
        out_dir = self._ti_output() or str(Path(path).parent)
        dpi = self._ti_dpi.currentData()
        self._run_worker(
            docx_to_images, path, out_dir, dpi, title="Converting to Images…"
        )

    # ------------------------------------------------------------------
    # Document Info panel
    # ------------------------------------------------------------------

    def _build_info_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        layout.addWidget(QLabel("Document Info", objectName="titleLabel"))
        layout.addWidget(QLabel("View metadata and statistics for a Word document.",
                                objectName="subtitleLabel"))

        in_group, self._info_input = self._single_file_picker(w)
        layout.addWidget(in_group)

        btn = QPushButton("Get Info")
        btn.setObjectName("primaryButton")
        btn.clicked.connect(self._run_info)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignLeft)

        self._info_display = QTextEdit()
        self._info_display.setReadOnly(True)
        self._info_display.setPlaceholderText("Document metadata will appear here…")
        layout.addWidget(self._info_display)
        return w

    def _run_info(self) -> None:
        path = self._info_input()
        if not path:
            QMessageBox.warning(self, "No File", "Please select a DOCX file.")
            return

        dlg = ProgressDialog("Reading document…", parent=self)
        worker = Worker(get_docx_info, path)
        worker.signals.result.connect(self._display_info)
        worker.signals.error.connect(lambda e: self._show_error(e, dlg))
        worker.signals.finished.connect(dlg.accept)
        QThreadPool.globalInstance().start(worker)
        dlg.exec()

    def _display_info(self, info: dict) -> None:
        lines = [
            f"Title:       {info.get('title', '—')}",
            f"Author:      {info.get('author', '—')}",
            f"Created:     {info.get('created', '—')}",
            f"Modified:    {info.get('modified', '—')}",
            f"Paragraphs:  {info.get('paragraphs', '—')}",
            f"Word count:  {info.get('words', '—')}",
        ]
        self._info_display.setPlainText("\n".join(lines))

    # ------------------------------------------------------------------
    # External API
    # ------------------------------------------------------------------

    def preload_files(self, paths: List[str]) -> None:
        self._nav.setCurrentRow(0)
