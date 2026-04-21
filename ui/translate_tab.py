"""
Translation tab – translate PDF and DOCX documents to other languages.
Follows the existing Enterprise Dark style and layout conventions.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List

from PyQt6.QtCore import Qt, QThreadPool
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import config
from core.worker import Worker
from services.document_translation_service import translate_document
from translation.translator import Translator
from utils.recent_files import RecentFiles

# Language display → code
_LANGS = {
    "Auto-detect": "auto",
    "English":     "en",
    "Romanian":    "ro",
    "Hungarian":   "hu",
}
_TARGET_LANGS = {k: v for k, v in _LANGS.items() if k != "Auto-detect"}

_PROVIDERS = {
    "LibreTranslate (local / self-hosted)": "libretranslate",
    "DeepL (API key required)":             "deepl",
    "Offline – MarianMT (HuggingFace)":     "marianmt",
}


class TranslateTab(QWidget):
    def __init__(self, recent_files: RecentFiles, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._recent = recent_files
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

        # ── Heading ──────────────────────────────────────────────────
        layout.addWidget(QLabel("Document Translation 🌍", objectName="titleLabel"))
        layout.addWidget(QLabel(
            "Translate PDF or Word documents between English, Romanian and Hungarian.",
            objectName="subtitleLabel",
        ))

        # ── Input file ───────────────────────────────────────────────
        file_group = QGroupBox("Input File")
        fg = QHBoxLayout(file_group)
        self._file_line = QLineEdit()
        self._file_line.setReadOnly(True)
        self._file_line.setPlaceholderText("Select a PDF or Word document…")
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_file)
        fg.addWidget(self._file_line, 1)
        fg.addWidget(browse_btn)
        layout.addWidget(file_group)

        # ── Language pair ─────────────────────────────────────────────
        lang_group = QGroupBox("Language")
        lg = QHBoxLayout(lang_group)
        lg.setSpacing(16)

        lg.addWidget(QLabel("Source:"))
        self._src_combo = QComboBox()
        for display in _LANGS:
            self._src_combo.addItem(display, _LANGS[display])
        self._src_combo.setCurrentText("Auto-detect")
        lg.addWidget(self._src_combo)

        arrow = QLabel("→")
        arrow.setStyleSheet("font-size:18px;color:#0078d4;font-weight:bold;")
        lg.addWidget(arrow)

        lg.addWidget(QLabel("Target:"))
        self._tgt_combo = QComboBox()
        for display in _TARGET_LANGS:
            self._tgt_combo.addItem(display, _TARGET_LANGS[display])
        self._tgt_combo.setCurrentText("Romanian")
        lg.addWidget(self._tgt_combo)
        lg.addStretch()
        layout.addWidget(lang_group)

        # ── Provider ──────────────────────────────────────────────────
        prov_group = QGroupBox("Translation Engine")
        pg = QVBoxLayout(prov_group)
        pg.setSpacing(10)

        prov_row = QHBoxLayout()
        prov_row.addWidget(QLabel("Provider:"))
        self._prov_combo = QComboBox()
        for display in _PROVIDERS:
            self._prov_combo.addItem(display, _PROVIDERS[display])
        self._prov_combo.currentIndexChanged.connect(self._on_provider_changed)
        prov_row.addWidget(self._prov_combo, 1)

        self._check_btn = QPushButton("Check Status")
        self._check_btn.setFixedWidth(110)
        self._check_btn.clicked.connect(self._check_provider)
        prov_row.addWidget(self._check_btn)
        pg.addLayout(prov_row)

        # Status indicator
        self._prov_status = QLabel("Status: not checked")
        self._prov_status.setStyleSheet("color:#9aa0ac;font-size:12px;")
        pg.addWidget(self._prov_status)

        # LibreTranslate URL
        self._lt_group = QGroupBox("LibreTranslate Settings")
        ltg = QVBoxLayout(self._lt_group)
        url_row = QHBoxLayout()
        url_row.addWidget(QLabel("URL:"))
        self._lt_url = QLineEdit(config.LIBRETRANSLATE_URL)
        url_row.addWidget(self._lt_url)
        key_row = QHBoxLayout()
        key_row.addWidget(QLabel("API Key (optional):"))
        self._lt_key = QLineEdit(config.LIBRETRANSLATE_API_KEY)
        self._lt_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._lt_key.setPlaceholderText("Leave blank for local instance")
        key_row.addWidget(self._lt_key)
        ltg.addLayout(url_row)
        ltg.addLayout(key_row)
        pg.addWidget(self._lt_group)

        # DeepL key
        self._dl_group = QGroupBox("DeepL Settings")
        dlg_l = QHBoxLayout(self._dl_group)
        dlg_l.addWidget(QLabel("API Key:"))
        self._dl_key = QLineEdit(config.DEEPL_API_KEY)
        self._dl_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._dl_key.setPlaceholderText("Paste your DeepL API key…")
        dlg_l.addWidget(self._dl_key)
        self._dl_group.setVisible(False)
        pg.addWidget(self._dl_group)

        layout.addWidget(prov_group)

        # ── Export options ────────────────────────────────────────────
        export_group = QGroupBox("Export")
        exg = QHBoxLayout(export_group)
        self._export_docx = QRadioButton("DOCX  (default)")
        self._export_pdf  = QRadioButton("DOCX + PDF")
        self._export_docx.setChecked(True)
        btn_grp = QButtonGroup(self)
        btn_grp.addButton(self._export_docx)
        btn_grp.addButton(self._export_pdf)
        exg.addWidget(self._export_docx)
        exg.addWidget(self._export_pdf)
        exg.addStretch()
        layout.addWidget(export_group)

        # ── Translate button ──────────────────────────────────────────
        self._translate_btn = QPushButton("Translate Document")
        self._translate_btn.setObjectName("primaryButton")
        self._translate_btn.setFixedHeight(40)
        self._translate_btn.clicked.connect(self._run_translation)
        layout.addWidget(self._translate_btn)

        # ── Progress ──────────────────────────────────────────────────
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        # ── Status log ────────────────────────────────────────────────
        log_group = QGroupBox("Status Log")
        log_layout = QVBoxLayout(log_group)
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(120)
        self._log.setMaximumHeight(200)
        self._log.setPlaceholderText("Translation progress will appear here…")
        self._log.setStyleSheet("font-family:'Consolas','Courier New',monospace;font-size:12px;")
        log_layout.addWidget(self._log)
        layout.addWidget(log_group)

        # MarianMT note
        self._marian_note = QLabel(
            "ℹ  Offline mode downloads ~300 MB of models on first use "
            "(cached to ~/.docprocessor/models/).\n"
            "   Install dependencies first:  pip install transformers sentencepiece torch"
        )
        self._marian_note.setStyleSheet("color:#9aa0ac;font-size:11px;")
        self._marian_note.setWordWrap(True)
        self._marian_note.setVisible(False)
        layout.addWidget(self._marian_note)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    # ------------------------------------------------------------------
    # Provider switching
    # ------------------------------------------------------------------

    def _on_provider_changed(self) -> None:
        name = self._prov_combo.currentData()
        self._lt_group.setVisible(name == "libretranslate")
        self._dl_group.setVisible(name == "deepl")
        self._marian_note.setVisible(name == "marianmt")
        self._prov_status.setText("Status: not checked")
        self._prov_status.setStyleSheet("color:#9aa0ac;font-size:12px;")

    def _check_provider(self) -> None:
        self._apply_provider_settings()
        t = Translator(provider=self._prov_combo.currentData())
        available, msg = t.check_availability()
        if available:
            self._prov_status.setText(f"✓  {msg}")
            self._prov_status.setStyleSheet("color:#4ec9b0;font-size:12px;")
        else:
            self._prov_status.setText(f"✗  {msg}")
            self._prov_status.setStyleSheet("color:#f14c4c;font-size:12px;")

    def _apply_provider_settings(self) -> None:
        """Write UI fields back into config (runtime only)."""
        config.LIBRETRANSLATE_URL     = self._lt_url.text().strip() or config.LIBRETRANSLATE_URL
        config.LIBRETRANSLATE_API_KEY = self._lt_key.text().strip()
        config.DEEPL_API_KEY          = self._dl_key.text().strip()

    # ------------------------------------------------------------------
    # File picker
    # ------------------------------------------------------------------

    def _browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Document", "",
            "Documents (*.pdf *.docx *.doc);;All Files (*)",
        )
        if path:
            self._file_line.setText(path)
            self._recent.add(path)

    # ------------------------------------------------------------------
    # Translation
    # ------------------------------------------------------------------

    def _run_translation(self) -> None:
        path = self._file_line.text().strip()
        if not path:
            QMessageBox.warning(self, "No File", "Please select a PDF or Word document.")
            return
        if not os.path.isfile(path):
            QMessageBox.warning(self, "File Not Found", f"Cannot find:\n{path}")
            return

        src = self._src_combo.currentData()
        tgt = self._tgt_combo.currentData()
        if src != "auto" and src == tgt:
            QMessageBox.warning(self, "Same Language",
                                "Source and target languages are the same.")
            return

        self._apply_provider_settings()
        provider   = self._prov_combo.currentData()
        export_pdf = self._export_pdf.isChecked()

        self._log.clear()
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._translate_btn.setEnabled(False)
        self._append_log(f"Starting translation: {Path(path).name}")
        self._append_log(f"Provider: {self._prov_combo.currentText()}")
        self._append_log(f"Direction: {src} → {tgt}\n")

        worker = Worker(
            translate_document,
            path,
            tgt,
            source_lang=src,
            provider=provider,
            export_pdf=export_pdf,
        )
        worker.signals.progress.connect(self._on_progress)
        worker.signals.status.connect(self._append_log)
        worker.signals.result.connect(self._on_done)
        worker.signals.error.connect(self._on_error)
        worker.signals.finished.connect(lambda: self._translate_btn.setEnabled(True))
        QThreadPool.globalInstance().start(worker)

    def _on_progress(self, value: int) -> None:
        self._progress_bar.setValue(value)

    def _append_log(self, msg: str) -> None:
        self._log.appendPlainText(msg)
        self._log.verticalScrollBar().setValue(
            self._log.verticalScrollBar().maximum()
        )

    def _on_done(self, output_path: str) -> None:
        self._progress_bar.setValue(100)
        self._append_log(f"\n✓  Translation complete!")
        self._append_log(f"   Saved to: {output_path}")
        QMessageBox.information(
            self, "Translation Complete",
            f"Document translated successfully.\n\nOutput:\n{output_path}",
        )

    def _on_error(self, error_text: str) -> None:
        self._progress_bar.setVisible(False)
        self._append_log(f"\n✗  Error:\n{error_text}")
        QMessageBox.critical(
            self, "Translation Failed",
            f"An error occurred:\n\n{error_text}\n\n"
            "Check the Status Log for details.",
        )

    # ------------------------------------------------------------------
    # External API
    # ------------------------------------------------------------------

    def preload_files(self, paths: List[str]) -> None:
        if paths:
            self._file_line.setText(paths[0])
