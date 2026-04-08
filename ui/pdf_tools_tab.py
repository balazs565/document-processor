"""
PDF Tools tab – all PDF operations organised into a left-nav / right-panel layout.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

from PyQt6.QtCore import Qt, QThreadPool
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QSplitter,
    QScrollArea,
)

from core import pdf_tools
from core.worker import Worker
from ui.widgets.drop_zone import DropZone
from ui.widgets.file_list import FileListWidget
from ui.widgets.progress_widget import ProgressDialog
from ui.page_arranger import PageArrangerWidget
from utils.file_utils import build_output_path, unique_path
from utils.recent_files import RecentFiles


class PDFToolsTab(QWidget):
    def __init__(self, recent_files: RecentFiles, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._recent = recent_files
        self._build_ui()

    # ------------------------------------------------------------------
    # UI skeleton (left nav + stacked pages)
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # Left navigation list
        self._nav = QListWidget()
        self._nav.setFixedWidth(180)
        self._nav.setStyleSheet(
            "QListWidget { background: #181825; border: none; border-right: 1px solid #313244; }"
            "QListWidget::item { padding: 10px 14px; color: #a6adc8; }"
            "QListWidget::item:selected { background: #313244; color: #7c6af5; font-weight: bold; }"
            "QListWidget::item:hover:!selected { background: #252537; color: #cdd6f4; }"
        )

        tools = [
            ("✂️  Split", "split"),
            ("🔀  Merge", "merge"),
            ("🗜️  Compress", "compress"),
            ("🖼️  Extract Images", "extract_images"),
            ("📝  Extract Text", "extract_text"),
            ("📄  Arrange Pages", "arrange"),
            ("🗑️  Delete Pages", "delete"),
            ("🔃  Rotate Pages", "rotate"),
            ("💧  Watermark", "watermark"),
            ("🔒  Add Password", "add_password"),
            ("🔓  Remove Password", "remove_password"),
        ]
        for label, key in tools:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self._nav.addItem(item)

        self._nav.currentRowChanged.connect(self._switch_panel)

        # Stacked panels
        self._stack = QStackedWidget()
        self._panels = {}
        panel_builders = {
            "split": self._build_split_panel,
            "merge": self._build_merge_panel,
            "compress": self._build_compress_panel,
            "extract_images": self._build_extract_images_panel,
            "extract_text": self._build_extract_text_panel,
            "arrange": self._build_arrange_panel,
            "delete": self._build_delete_panel,
            "rotate": self._build_rotate_panel,
            "watermark": self._build_watermark_panel,
            "add_password": self._build_add_password_panel,
            "remove_password": self._build_remove_password_panel,
        }
        for _, key in tools:
            panel = panel_builders[key]()
            self._stack.addWidget(panel)
            self._panels[key] = self._stack.count() - 1

        main.addWidget(self._nav)
        main.addWidget(self._stack)
        self._nav.setCurrentRow(0)

    def _switch_panel(self, row: int) -> None:
        self._stack.setCurrentIndex(row)

    # ------------------------------------------------------------------
    # Helpers shared across panels
    # ------------------------------------------------------------------

    def _scroll_wrap(self, widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidget(widget)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        return scroll

    def _single_file_picker(self, label_text: str, ext_filter: str, parent: QWidget) -> tuple:
        """Returns (group_widget, getter_fn) for a single PDF file chooser."""
        group = QGroupBox("Input File")
        gl = QHBoxLayout(group)
        line = QLineEdit()
        line.setReadOnly(True)
        line.setPlaceholderText("Select a PDF…")
        btn = QPushButton("Browse…")

        def browse():
            path, _ = QFileDialog.getOpenFileName(parent, "Select PDF", "", ext_filter)
            if path:
                line.setText(path)
                self._recent.add(path)

        btn.clicked.connect(browse)
        gl.addWidget(line, 1)
        gl.addWidget(btn)
        return group, lambda: line.text()

    def _output_dir_picker(self, parent: QWidget) -> tuple:
        """Returns (group_widget, getter_fn) for an output directory chooser."""
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

    def _run_worker(self, fn, *args, title="Processing…", **kwargs) -> None:
        """Generic helper: run *fn* in background, show progress dialog."""
        dlg = ProgressDialog(title, parent=self)
        self._last_error: str | None = None

        worker = Worker(fn, *args, **kwargs)
        worker.signals.progress.connect(dlg.set_progress)
        worker.signals.status.connect(dlg.set_status)
        worker.signals.result.connect(lambda r: self._show_result(r))
        worker.signals.error.connect(lambda e: self._show_error(e, dlg))
        worker.signals.finished.connect(dlg.accept)

        QThreadPool.globalInstance().start(worker)
        dlg.exec()

    def _show_result(self, result) -> None:
        if isinstance(result, list):
            msg = f"Done! {len(result)} file(s) created."
        elif isinstance(result, str):
            msg = f"Done!\nOutput: {result}"
        else:
            msg = "Operation completed."
        QMessageBox.information(self, "Done", msg)

    def _show_error(self, error_text: str, dlg: ProgressDialog | None = None) -> None:
        if dlg:
            dlg.accept()
        QMessageBox.critical(self, "Error", f"Operation failed:\n\n{error_text}")

    # ==================================================================
    # Panel builders
    # ==================================================================

    # -- Split ----------------------------------------------------------

    def _build_split_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        layout.addWidget(QLabel("Split PDF", objectName="titleLabel"))
        layout.addWidget(QLabel("Divide a PDF by page ranges or into individual pages.",
                                objectName="subtitleLabel"))

        in_group, self._split_input = self._single_file_picker(
            "Input PDF", "PDF Files (*.pdf)", w
        )
        layout.addWidget(in_group)

        mode_group = QGroupBox("Split Mode")
        ml = QVBoxLayout(mode_group)
        self._split_individual = QCheckBox("Split into individual pages (one PDF per page)")
        ranges_row = QHBoxLayout()
        ranges_row.addWidget(QLabel("Or enter page ranges (e.g. 1-3,5,7-10):"))
        self._split_ranges = QLineEdit()
        self._split_ranges.setPlaceholderText("1-3, 5, 7-10")
        ranges_row.addWidget(self._split_ranges)
        ml.addWidget(self._split_individual)
        ml.addLayout(ranges_row)
        layout.addWidget(mode_group)

        out_group, self._split_output = self._output_dir_picker(w)
        layout.addWidget(out_group)

        btn = QPushButton("Split PDF")
        btn.setObjectName("primaryButton")
        btn.clicked.connect(self._run_split)
        layout.addWidget(btn)
        layout.addStretch()
        return w

    def _run_split(self) -> None:
        path = self._split_input()
        if not path:
            QMessageBox.warning(self, "No File", "Please select a PDF.")
            return

        individual = self._split_individual.isChecked()
        ranges_text = self._split_ranges.text().strip()
        ranges = None
        if not individual and ranges_text:
            try:
                ranges = self._parse_ranges(ranges_text)
            except ValueError as e:
                QMessageBox.warning(self, "Invalid Range", str(e))
                return

        out_dir = self._split_output() or str(Path(path).parent)
        self._run_worker(
            pdf_tools.split_pdf, path, out_dir, ranges, individual, title="Splitting PDF…"
        )

    @staticmethod
    def _parse_ranges(text: str) -> List[tuple]:
        ranges = []
        for part in text.split(","):
            part = part.strip()
            if "-" in part:
                s, e = part.split("-", 1)
                ranges.append((int(s.strip()), int(e.strip())))
            elif part.isdigit():
                n = int(part)
                ranges.append((n, n))
            else:
                raise ValueError(f"Invalid range: {part!r}")
        return ranges

    # -- Merge ----------------------------------------------------------

    def _build_merge_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        layout.addWidget(QLabel("Merge PDFs", objectName="titleLabel"))
        layout.addWidget(QLabel("Combine multiple PDFs into one. Drag to reorder files.",
                                objectName="subtitleLabel"))

        drop = DropZone("Drop PDF files here", accepted_extensions=[".pdf"])
        drop.files_dropped.connect(lambda paths: self._merge_list.add_files(paths))
        layout.addWidget(drop)

        self._merge_list = FileListWidget(accepted_extensions=[".pdf"], allow_reorder=True)
        layout.addWidget(self._merge_list)

        add_btn = QPushButton("Add PDFs…")
        add_btn.clicked.connect(self._browse_merge_files)
        layout.addWidget(add_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Output file:"))
        self._merge_out = QLineEdit()
        self._merge_out.setPlaceholderText("merged.pdf")
        browse_out = QPushButton("Browse…")
        browse_out.clicked.connect(self._browse_merge_output)
        out_row.addWidget(self._merge_out, 1)
        out_row.addWidget(browse_out)
        layout.addLayout(out_row)

        btn = QPushButton("Merge PDFs")
        btn.setObjectName("primaryButton")
        btn.clicked.connect(self._run_merge)
        layout.addWidget(btn)
        layout.addStretch()
        return w

    def _browse_merge_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Select PDFs", "", "PDF Files (*.pdf)")
        if paths:
            self._merge_list.add_files(paths)

    def _browse_merge_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save Merged PDF", "merged.pdf",
                                              "PDF Files (*.pdf)")
        if path:
            self._merge_out.setText(path)

    def _run_merge(self) -> None:
        files = self._merge_list.get_files()
        if len(files) < 2:
            QMessageBox.warning(self, "Not Enough Files", "Add at least 2 PDFs to merge.")
            return
        out = self._merge_out.text().strip() or unique_path("merged.pdf")
        self._run_worker(pdf_tools.merge_pdfs, files, out, title="Merging PDFs…")

    # -- Compress -------------------------------------------------------

    def _build_compress_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        layout.addWidget(QLabel("Compress PDF", objectName="titleLabel"))
        layout.addWidget(QLabel("Re-encode pages as JPEG to reduce file size.",
                                objectName="subtitleLabel"))

        in_group, self._compress_input = self._single_file_picker(
            "Input PDF", "PDF Files (*.pdf)", w
        )
        layout.addWidget(in_group)

        quality_group = QGroupBox("Compression Quality")
        ql = QVBoxLayout(quality_group)
        quality_row = QHBoxLayout()
        self._compress_slider = QSlider(Qt.Orientation.Horizontal)
        self._compress_slider.setRange(10, 95)
        self._compress_slider.setValue(75)
        self._compress_slider.setTickInterval(5)
        self._compress_label = QLabel("75%")
        self._compress_label.setFixedWidth(40)
        self._compress_slider.valueChanged.connect(
            lambda v: self._compress_label.setText(f"{v}%")
        )
        quality_row.addWidget(QLabel("Low (small file)"))
        quality_row.addWidget(self._compress_slider, 1)
        quality_row.addWidget(QLabel("High (large file)"))
        quality_row.addWidget(self._compress_label)
        ql.addLayout(quality_row)
        layout.addWidget(quality_group)

        out_group, self._compress_output = self._output_dir_picker(w)
        layout.addWidget(out_group)

        btn = QPushButton("Compress PDF")
        btn.setObjectName("primaryButton")
        btn.clicked.connect(self._run_compress)
        layout.addWidget(btn)
        layout.addStretch()
        return w

    def _run_compress(self) -> None:
        path = self._compress_input()
        if not path:
            QMessageBox.warning(self, "No File", "Please select a PDF.")
            return
        out_dir = self._compress_output() or str(Path(path).parent)
        stem = Path(path).stem
        out = unique_path(os.path.join(out_dir, f"{stem}_compressed.pdf"))
        quality = self._compress_slider.value()
        self._run_worker(pdf_tools.compress_pdf, path, out, quality, title="Compressing…")

    # -- Extract Images ------------------------------------------------

    def _build_extract_images_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        layout.addWidget(QLabel("Extract Images", objectName="titleLabel"))
        layout.addWidget(QLabel("Save all embedded images from a PDF to a folder.",
                                objectName="subtitleLabel"))

        in_group, self._ext_img_input = self._single_file_picker(
            "Input PDF", "PDF Files (*.pdf)", w
        )
        layout.addWidget(in_group)

        out_group, self._ext_img_output = self._output_dir_picker(w)
        layout.addWidget(out_group)

        btn = QPushButton("Extract Images")
        btn.setObjectName("primaryButton")
        btn.clicked.connect(self._run_extract_images)
        layout.addWidget(btn)
        layout.addStretch()
        return w

    def _run_extract_images(self) -> None:
        path = self._ext_img_input()
        if not path:
            QMessageBox.warning(self, "No File", "Please select a PDF.")
            return
        out_dir = self._ext_img_output() or str(Path(path).parent)
        self._run_worker(
            pdf_tools.extract_images_from_pdf, path, out_dir, title="Extracting Images…"
        )

    # -- Extract Text --------------------------------------------------

    def _build_extract_text_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        layout.addWidget(QLabel("Extract Text", objectName="titleLabel"))
        layout.addWidget(QLabel("Extract selectable text from a PDF.",
                                objectName="subtitleLabel"))

        in_group, self._ext_txt_input = self._single_file_picker(
            "Input PDF", "PDF Files (*.pdf)", w
        )
        layout.addWidget(in_group)

        btn = QPushButton("Extract Text")
        btn.setObjectName("primaryButton")
        btn.clicked.connect(self._run_extract_text)
        layout.addWidget(btn)

        self._text_preview = QTextEdit()
        self._text_preview.setReadOnly(True)
        self._text_preview.setPlaceholderText("Extracted text will appear here…")
        layout.addWidget(self._text_preview)

        save_btn = QPushButton("Save as .txt…")
        save_btn.clicked.connect(self._save_text)
        layout.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        return w

    def _run_extract_text(self) -> None:
        path = self._ext_txt_input()
        if not path:
            QMessageBox.warning(self, "No File", "Please select a PDF.")
            return

        dlg = ProgressDialog("Extracting Text…", parent=self)
        worker = Worker(pdf_tools.extract_text_from_pdf, path)
        worker.signals.progress.connect(dlg.set_progress)
        worker.signals.status.connect(dlg.set_status)
        worker.signals.result.connect(
            lambda t: self._text_preview.setPlainText(t)
        )
        worker.signals.error.connect(lambda e: self._show_error(e, dlg))
        worker.signals.finished.connect(dlg.accept)
        QThreadPool.globalInstance().start(worker)
        dlg.exec()

    def _save_text(self) -> None:
        text = self._text_preview.toPlainText()
        if not text:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Text", "extracted.txt",
                                              "Text Files (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)

    # -- Arrange Pages -------------------------------------------------

    def _build_arrange_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QWidget()
        toolbar.setStyleSheet("background: #181825; padding: 8px;")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(16, 8, 16, 8)

        heading = QLabel("Arrange Pages")
        heading.setObjectName("titleLabel")
        tb.addWidget(heading)
        tb.addStretch()

        load_btn = QPushButton("Load PDF…")
        load_btn.clicked.connect(self._load_arrange_pdf)
        save_btn = QPushButton("Save Reordered PDF…")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._save_arranged_pdf)
        tb.addWidget(load_btn)
        tb.addWidget(save_btn)

        self._arranger = PageArrangerWidget()
        self._arrange_source: str | None = None
        self._arrange_source_path = ""

        layout.addWidget(toolbar)
        layout.addWidget(self._arranger)
        return w

    def _load_arrange_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load PDF", "", "PDF Files (*.pdf)")
        if path:
            self._arrange_source_path = path
            self._recent.add(path)
            try:
                self._arranger.load_pdf(path)
            except Exception as exc:
                QMessageBox.critical(self, "Error", f"Could not load PDF:\n{exc}")

    def _save_arranged_pdf(self) -> None:
        if not self._arrange_source_path:
            QMessageBox.warning(self, "No PDF", "Load a PDF first.")
            return
        order = self._arranger.get_current_order()
        out, _ = QFileDialog.getSaveFileName(
            self, "Save Reordered PDF",
            unique_path(
                build_output_path(self._arrange_source_path, None, ".pdf", "reordered")
            ),
            "PDF Files (*.pdf)",
        )
        if out:
            self._run_worker(
                pdf_tools.rearrange_pages,
                self._arrange_source_path, out, order,
                title="Saving…",
            )

    # -- Delete Pages --------------------------------------------------

    def _build_delete_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        layout.addWidget(QLabel("Delete Pages", objectName="titleLabel"))
        layout.addWidget(QLabel("Remove specific pages from a PDF.",
                                objectName="subtitleLabel"))

        in_group, self._del_input = self._single_file_picker(
            "Input PDF", "PDF Files (*.pdf)", w
        )
        layout.addWidget(in_group)

        pg_group = QGroupBox("Pages to Delete (1-based)")
        pg_layout = QVBoxLayout(pg_group)
        pg_layout.addWidget(QLabel("Enter page numbers separated by commas (e.g. 1, 3, 5-7):"))
        self._del_pages = QLineEdit()
        self._del_pages.setPlaceholderText("1, 3, 5-7")
        pg_layout.addWidget(self._del_pages)
        layout.addWidget(pg_group)

        out_group, self._del_output = self._output_dir_picker(w)
        layout.addWidget(out_group)

        btn = QPushButton("Delete Pages")
        btn.setObjectName("primaryButton")
        btn.clicked.connect(self._run_delete_pages)
        layout.addWidget(btn)
        layout.addStretch()
        return w

    def _run_delete_pages(self) -> None:
        path = self._del_input()
        if not path:
            QMessageBox.warning(self, "No File", "Please select a PDF.")
            return
        try:
            ranges = self._parse_ranges(self._del_pages.text())
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Input", str(e))
            return

        pages = []
        for s, e in ranges:
            pages.extend(range(s - 1, e))  # convert to 0-based

        out_dir = self._del_output() or str(Path(path).parent)
        out = unique_path(os.path.join(out_dir, f"{Path(path).stem}_deleted.pdf"))
        self._run_worker(pdf_tools.delete_pages, path, out, pages, title="Deleting Pages…")

    # -- Rotate Pages --------------------------------------------------

    def _build_rotate_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        layout.addWidget(QLabel("Rotate Pages", objectName="titleLabel"))
        layout.addWidget(QLabel("Rotate specific pages or all pages.",
                                objectName="subtitleLabel"))

        in_group, self._rot_input = self._single_file_picker(
            "Input PDF", "PDF Files (*.pdf)", w
        )
        layout.addWidget(in_group)

        rot_group = QGroupBox("Rotation Settings")
        rl = QVBoxLayout(rot_group)

        all_row = QHBoxLayout()
        all_row.addWidget(QLabel("Apply rotation to all pages:"))
        self._rot_all_combo = QComboBox()
        for label in ["No rotation", "90° clockwise", "180°", "270° clockwise"]:
            self._rot_all_combo.addItem(label, [0, 90, 180, 270][["No rotation", "90° clockwise", "180°", "270° clockwise"].index(label)])
        all_row.addWidget(self._rot_all_combo)
        all_row.addStretch()

        specific_row = QHBoxLayout()
        specific_row.addWidget(QLabel("Or rotate specific pages (e.g. 1-3:90, 5:180):"))
        self._rot_specific = QLineEdit()
        self._rot_specific.setPlaceholderText("1-3:90, 5:180")
        specific_row.addWidget(self._rot_specific)

        rl.addLayout(all_row)
        rl.addLayout(specific_row)
        layout.addWidget(rot_group)

        out_group, self._rot_output = self._output_dir_picker(w)
        layout.addWidget(out_group)

        btn = QPushButton("Rotate Pages")
        btn.setObjectName("primaryButton")
        btn.clicked.connect(self._run_rotate)
        layout.addWidget(btn)
        layout.addStretch()
        return w

    def _run_rotate(self) -> None:
        path = self._rot_input()
        if not path:
            QMessageBox.warning(self, "No File", "Please select a PDF.")
            return

        rotations: dict = {}
        specific = self._rot_specific.text().strip()
        all_deg = self._rot_all_combo.currentData()

        if specific:
            # parse "1-3:90, 5:180"
            try:
                for part in specific.split(","):
                    part = part.strip()
                    pages_str, deg_str = part.split(":")
                    deg = int(deg_str.strip())
                    for s, e in self._parse_ranges(pages_str.strip()):
                        for pg in range(s - 1, e):
                            rotations[pg] = deg
            except Exception as exc:
                QMessageBox.warning(self, "Invalid Input", str(exc))
                return
        elif all_deg:
            import fitz
            with fitz.open(path) as doc:
                for i in range(doc.page_count):
                    rotations[i] = all_deg
        else:
            QMessageBox.information(self, "Nothing to do", "No rotation specified.")
            return

        out_dir = self._rot_output() or str(Path(path).parent)
        out = unique_path(os.path.join(out_dir, f"{Path(path).stem}_rotated.pdf"))
        self._run_worker(pdf_tools.rotate_pages, path, out, rotations, title="Rotating…")

    # -- Watermark -----------------------------------------------------

    def _build_watermark_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        layout.addWidget(QLabel("Add Watermark", objectName="titleLabel"))
        layout.addWidget(QLabel("Add a text or image watermark to every page.",
                                objectName="subtitleLabel"))

        in_group, self._wm_input = self._single_file_picker(
            "Input PDF", "PDF Files (*.pdf)", w
        )
        layout.addWidget(in_group)

        wm_group = QGroupBox("Watermark Options")
        wl = QVBoxLayout(wm_group)

        text_row = QHBoxLayout()
        text_row.addWidget(QLabel("Text watermark:"))
        self._wm_text = QLineEdit()
        self._wm_text.setPlaceholderText("e.g. CONFIDENTIAL")
        text_row.addWidget(self._wm_text)

        img_row = QHBoxLayout()
        img_row.addWidget(QLabel("Or image watermark:"))
        self._wm_img = QLineEdit()
        self._wm_img.setReadOnly(True)
        browse_img = QPushButton("Browse…")
        browse_img.clicked.connect(self._browse_wm_image)
        img_row.addWidget(self._wm_img, 1)
        img_row.addWidget(browse_img)

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Font size:"))
        self._wm_size = QSpinBox()
        self._wm_size.setRange(10, 200)
        self._wm_size.setValue(60)
        size_row.addWidget(self._wm_size)
        size_row.addStretch()

        wl.addLayout(text_row)
        wl.addLayout(img_row)
        wl.addLayout(size_row)
        layout.addWidget(wm_group)

        out_group, self._wm_output = self._output_dir_picker(w)
        layout.addWidget(out_group)

        btn = QPushButton("Add Watermark")
        btn.setObjectName("primaryButton")
        btn.clicked.connect(self._run_watermark)
        layout.addWidget(btn)
        layout.addStretch()
        return w

    def _browse_wm_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Watermark Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if path:
            self._wm_img.setText(path)

    def _run_watermark(self) -> None:
        path = self._wm_input()
        if not path:
            QMessageBox.warning(self, "No File", "Please select a PDF.")
            return
        text = self._wm_text.text().strip() or None
        img = self._wm_img.text().strip() or None
        if not text and not img:
            QMessageBox.warning(self, "No Watermark", "Enter text or choose an image.")
            return
        out_dir = self._wm_output() or str(Path(path).parent)
        out = unique_path(os.path.join(out_dir, f"{Path(path).stem}_watermarked.pdf"))
        self._run_worker(
            pdf_tools.add_watermark, path, out, text, img,
            font_size=self._wm_size.value(), title="Adding Watermark…"
        )

    # -- Add Password --------------------------------------------------

    def _build_add_password_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        layout.addWidget(QLabel("Add Password Protection", objectName="titleLabel"))
        layout.addWidget(QLabel("Encrypt the PDF with AES-256.",
                                objectName="subtitleLabel"))

        in_group, self._pw_add_input = self._single_file_picker(
            "Input PDF", "PDF Files (*.pdf)", w
        )
        layout.addWidget(in_group)

        pw_group = QGroupBox("Password")
        pl = QVBoxLayout(pw_group)
        self._pw_add = QLineEdit()
        self._pw_add.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw_add.setPlaceholderText("Enter password…")
        self._pw_add_confirm = QLineEdit()
        self._pw_add_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw_add_confirm.setPlaceholderText("Confirm password…")
        pl.addWidget(QLabel("Password:"))
        pl.addWidget(self._pw_add)
        pl.addWidget(QLabel("Confirm:"))
        pl.addWidget(self._pw_add_confirm)
        layout.addWidget(pw_group)

        out_group, self._pw_add_output = self._output_dir_picker(w)
        layout.addWidget(out_group)

        btn = QPushButton("Add Password")
        btn.setObjectName("primaryButton")
        btn.clicked.connect(self._run_add_password)
        layout.addWidget(btn)
        layout.addStretch()
        return w

    def _run_add_password(self) -> None:
        path = self._pw_add_input()
        if not path:
            QMessageBox.warning(self, "No File", "Please select a PDF.")
            return
        pw = self._pw_add.text()
        if not pw:
            QMessageBox.warning(self, "No Password", "Enter a password.")
            return
        if pw != self._pw_add_confirm.text():
            QMessageBox.warning(self, "Mismatch", "Passwords do not match.")
            return
        out_dir = self._pw_add_output() or str(Path(path).parent)
        out = unique_path(os.path.join(out_dir, f"{Path(path).stem}_protected.pdf"))
        self._run_worker(pdf_tools.add_password, path, out, pw, title="Encrypting…")

    # -- Remove Password -----------------------------------------------

    def _build_remove_password_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        layout.addWidget(QLabel("Remove Password", objectName="titleLabel"))
        layout.addWidget(QLabel("Decrypt a password-protected PDF (password required).",
                                objectName="subtitleLabel"))

        in_group, self._pw_rm_input = self._single_file_picker(
            "Input PDF", "PDF Files (*.pdf)", w
        )
        layout.addWidget(in_group)

        pw_group = QGroupBox("Current Password")
        pl = QVBoxLayout(pw_group)
        self._pw_rm = QLineEdit()
        self._pw_rm.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw_rm.setPlaceholderText("Enter current password…")
        pl.addWidget(self._pw_rm)
        layout.addWidget(pw_group)

        out_group, self._pw_rm_output = self._output_dir_picker(w)
        layout.addWidget(out_group)

        btn = QPushButton("Remove Password")
        btn.setObjectName("primaryButton")
        btn.clicked.connect(self._run_remove_password)
        layout.addWidget(btn)
        layout.addStretch()
        return w

    def _run_remove_password(self) -> None:
        path = self._pw_rm_input()
        if not path:
            QMessageBox.warning(self, "No File", "Please select a PDF.")
            return
        pw = self._pw_rm.text()
        if not pw:
            QMessageBox.warning(self, "No Password", "Enter the current password.")
            return
        out_dir = self._pw_rm_output() or str(Path(path).parent)
        out = unique_path(os.path.join(out_dir, f"{Path(path).stem}_unlocked.pdf"))
        self._run_worker(pdf_tools.remove_password, path, out, pw, title="Decrypting…")

    # ------------------------------------------------------------------
    # External API
    # ------------------------------------------------------------------

    def preload_files(self, paths: List[str]) -> None:
        """Navigate to merge panel and pre-load files."""
        self._nav.setCurrentRow(1)  # Merge panel
        self._merge_list.add_files(paths)
