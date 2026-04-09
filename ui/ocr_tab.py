"""
OCR tab – extract text from scanned PDFs and images.
Layout is scroll-wrapped so file additions don't collapse options.
"""
from __future__ import annotations

import os
from typing import List

from PyQt6.QtCore import Qt, QThreadPool
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
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
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(18)

        layout.addWidget(QLabel("OCR – Text Recognition", objectName="titleLabel"))
        layout.addWidget(QLabel(
            "Extract text from scanned PDFs or images. "
            "Romanian and Hungarian language packs supported.",
            objectName="subtitleLabel"
        ))

        # Language settings
        lang_group = QGroupBox("Language Settings")
        lg = QVBoxLayout(lang_group)
        lg.setSpacing(10)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Primary language:"))
        self._lang_combo = QComboBox()
        for display, code in config.OCR_LANGUAGES.items():
            self._lang_combo.addItem(display, code)
        self._lang_combo.setCurrentText("Romanian")
        row1.addWidget(self._lang_combo)
        row1.addStretch()

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Also include English:"))
        self._eng_check = QCheckBox()
        row2.addWidget(self._eng_check)
        row2.addStretch()

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Scan resolution (DPI):"))
        self._dpi_combo = QComboBox()
        for dpi in ["150", "200", "300", "400", "600"]:
            self._dpi_combo.addItem(f"{dpi} DPI", int(dpi))
        self._dpi_combo.setCurrentText("300 DPI")
        row3.addWidget(self._dpi_combo)
        row3.addStretch()

        lg.addLayout(row1)
        lg.addLayout(row2)
        lg.addLayout(row3)
        layout.addWidget(lang_group)

        # Drop zone – fixed height
        self._drop_zone = DropZone(
            "Drop PDF or image files here",
            accepted_extensions=[".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"],
        )
        self._drop_zone.setFixedHeight(120)
        self._drop_zone.files_dropped.connect(self._add_files)
        layout.addWidget(self._drop_zone)

        # File list – constrained
        files_group = QGroupBox("Files to Process")
        fl = QVBoxLayout(files_group)
        self._file_list = FileListWidget(
            accepted_extensions=[".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"]
        )
        self._file_list.setMinimumHeight(100)
        self._file_list.setMaximumHeight(200)
        fl.addWidget(self._file_list)
        add_btn = QPushButton("Add Files…")
        add_btn.clicked.connect(self._browse_files)
        fl.addWidget(add_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(files_group)

        # Output
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

        # Run button
        self._run_btn = QPushButton("Run OCR")
        self._run_btn.setObjectName("primaryButton")
        self._run_btn.setFixedHeight(38)
        self._run_btn.clicked.connect(self._run_ocr)
        layout.addWidget(self._run_btn)

        note = QLabel(
            "⚠  Tesseract OCR must be installed with ron and hun language packs. "
            "See README for installation instructions."
        )
        note.setStyleSheet("color:#d7ba7d;font-size:11px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _add_files(self, paths: List[str]) -> None:
        self._file_list.add_files(paths)
        for p in paths:
            self._recent.add(p)

    def _browse_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Files", "",
            "PDF & Images (*.pdf *.png *.jpg *.jpeg *.tiff *.bmp);;All Files (*)",
        )
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
        dpi  = self._dpi_combo.currentData()
        successes: List[str] = []
        errors:    List[str] = []

        dlg = ProgressDialog("Running OCR…", parent=self)

        def run_all(progress_callback, status_callback):
            total = len(files)
            for idx, fp in enumerate(files):
                out = None
                if self._output_dir:
                    stem = os.path.splitext(os.path.basename(fp))[0]
                    out  = os.path.join(self._output_dir, f"{stem}_ocr.docx")
                try:
                    status_callback(f"OCR: {os.path.basename(fp)} ({idx+1}/{total})…")
                    result = perform_ocr(
                        fp, language=lang, output_path=out, dpi=dpi,
                        progress_callback=lambda p: progress_callback(
                            int(((idx + p / 100) / total) * 100)
                        ),
                        status_callback=status_callback,
                    )
                    successes.append(result)
                except Exception as exc:
                    errors.append(f"{os.path.basename(fp)}: {exc}")
            return (successes, errors)

        worker = Worker(run_all)
        worker.signals.progress.connect(dlg.set_progress)
        worker.signals.status.connect(dlg.set_status)
        worker.signals.result.connect(lambda r: self._on_done(r[0], r[1]))
        worker.signals.error.connect(lambda e: (dlg.accept(), self._on_error(e)))
        worker.signals.finished.connect(dlg.accept)
        QThreadPool.globalInstance().start(worker)
        dlg.exec()

    def _on_done(self, successes, errors) -> None:
        msg = f"✓  OCR completed for {len(successes)} file(s)."
        if errors:
            msg += f"\n\n✗  {len(errors)} error(s):\n" + "\n".join(f"  • {e}" for e in errors)
        QMessageBox.information(self, "Done", msg)

    def _on_error(self, error_text: str) -> None:
        QMessageBox.critical(self, "Error", f"OCR failed:\n\n{error_text}")

    def preload_files(self, paths: List[str]) -> None:
        self._add_files(paths)
