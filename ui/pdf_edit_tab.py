"""
PDF Edit tab – annotate, add text, stamps and redactions to PDFs.

Tools available:
  • Sticky Note    – adds a PDF text-annotation at a clicked position
  • Free Text      – places a visible text box on the page
  • Highlight      – draws a coloured rectangle overlay
  • Stamp          – inserts APPROVED / DRAFT / CONFIDENTIAL diagonal text
  • Redact         – blacks-out a rectangle (permanent)
  • Erase Annots   – removes all annotations from the document

Workflow:
  1. Load a PDF via "Open PDF…"
  2. Navigate pages with the toolbar
  3. Pick a tool, configure its options, then click on the page preview
  4. Save with "Save As…"
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Tuple

import fitz
from PyQt6.QtCore import Qt, QPoint, QRect, QSize, pyqtSignal
from PyQt6.QtGui import (
    QColor, QCursor, QImage, QMouseEvent, QPainter,
    QPen, QPixmap, QBrush,
)
from PyQt6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from utils.file_utils import unique_path
from utils.recent_files import RecentFiles
from utils.logger import get_logger

logger = get_logger("pdf_edit_tab")

# ---------------------------------------------------------------------------
# Interactive page canvas
# ---------------------------------------------------------------------------

class PageCanvas(QLabel):
    """
    Renders one PDF page and captures mouse clicks/drags to place annotations.

    Emits:
        point_clicked(QPoint)         – single click (note / stamp tools)
        rect_selected(QRect)          – drag rectangle (highlight / redact)
    """
    point_clicked = pyqtSignal(QPoint)
    rect_selected  = pyqtSignal(QRect)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setStyleSheet("background:#2d3139;border:none;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._drag_start: Optional[QPoint] = None
        self._drag_rect: Optional[QRect] = None
        self._overlay_pixmap: Optional[QPixmap] = None
        self._drag_mode = False  # True for rect tools, False for point tools

    def set_drag_mode(self, enabled: bool) -> None:
        self._drag_mode = enabled

    def set_page_pixmap(self, pix: QPixmap) -> None:
        self._overlay_pixmap = pix
        self._drag_rect = None
        self._render()

    def _render(self) -> None:
        if self._overlay_pixmap is None:
            return
        combined = self._overlay_pixmap.copy()
        if self._drag_rect:
            painter = QPainter(combined)
            painter.setPen(QPen(QColor("#0078d4"), 2, Qt.PenStyle.DashLine))
            painter.setBrush(QBrush(QColor(0, 120, 212, 40)))
            painter.drawRect(self._drag_rect)
            painter.end()
        self.setPixmap(combined)

    # Mouse events
    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_start = e.position().toPoint()
            if not self._drag_mode:
                self.point_clicked.emit(self._drag_start)

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if self._drag_mode and self._drag_start:
            self._drag_rect = QRect(self._drag_start, e.position().toPoint()).normalized()
            self._render()

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if self._drag_mode and self._drag_start and self._drag_rect:
            self.rect_selected.emit(self._drag_rect)
            self._drag_rect = None
            self._drag_start = None
            self._render()

    def canvas_to_page(self, pt: QPoint, page_rect: fitz.Rect, scale: float) -> fitz.Point:
        """Convert canvas pixel coords → PDF page coords."""
        x = pt.x() / scale
        y = pt.y() / scale
        return fitz.Point(
            page_rect.x0 + x,
            page_rect.y0 + y,
        )

    def canvas_rect_to_page(self, rect: QRect, page_rect: fitz.Rect, scale: float) -> fitz.Rect:
        x0 = page_rect.x0 + rect.left()  / scale
        y0 = page_rect.y0 + rect.top()   / scale
        x1 = page_rect.x0 + rect.right() / scale
        y1 = page_rect.y0 + rect.bottom()/ scale
        return fitz.Rect(x0, y0, x1, y1)


# ---------------------------------------------------------------------------
# Main tab
# ---------------------------------------------------------------------------

class PDFEditTab(QWidget):
    def __init__(self, recent_files: RecentFiles, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._recent = recent_files
        self._doc: Optional[fitz.Document] = None
        self._doc_path: str = ""
        self._current_page = 0
        self._zoom = 1.5
        self._active_tool = "note"
        self._annot_color = QColor("#f9e2af")  # yellow default
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top toolbar ──────────────────────────────────────────────
        toolbar = QWidget()
        toolbar.setFixedHeight(52)
        toolbar.setStyleSheet(
            "background:#252830;border-bottom:1px solid #3a3f4b;"
        )
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(14, 8, 14, 8)
        tb.setSpacing(8)

        open_btn = QPushButton("Open PDF…")
        open_btn.clicked.connect(self._open_pdf)

        self._save_btn = QPushButton("Save As…")
        self._save_btn.setObjectName("primaryButton")
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save_pdf)

        self._prev_btn = QPushButton("◀")
        self._prev_btn.setFixedWidth(32)
        self._prev_btn.setEnabled(False)
        self._prev_btn.clicked.connect(self._prev_page)

        self._page_spin = QSpinBox()
        self._page_spin.setMinimum(1)
        self._page_spin.setFixedWidth(58)
        self._page_spin.setEnabled(False)
        self._page_spin.valueChanged.connect(self._go_to_page)

        self._total_lbl = QLabel("/ 0")
        self._total_lbl.setStyleSheet("color:#9aa0ac;")

        self._next_btn = QPushButton("▶")
        self._next_btn.setFixedWidth(32)
        self._next_btn.setEnabled(False)
        self._next_btn.clicked.connect(self._next_page)

        zoom_out = QPushButton("−")
        zoom_out.setFixedWidth(32)
        zoom_out.clicked.connect(self._zoom_out)
        zoom_in  = QPushButton("+")
        zoom_in.setFixedWidth(32)
        zoom_in.clicked.connect(self._zoom_in)
        self._zoom_lbl = QLabel("150%")
        self._zoom_lbl.setFixedWidth(42)
        self._zoom_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        tb.addWidget(open_btn)
        tb.addWidget(self._save_btn)
        tb.addWidget(QFrame(frameShape=QFrame.Shape.VLine,
                            styleSheet="color:#3a3f4b;max-width:1px;"))
        tb.addWidget(self._prev_btn)
        tb.addWidget(self._page_spin)
        tb.addWidget(self._total_lbl)
        tb.addWidget(self._next_btn)
        tb.addStretch()
        tb.addWidget(zoom_out)
        tb.addWidget(self._zoom_lbl)
        tb.addWidget(zoom_in)

        root.addWidget(toolbar)

        # ── Body: tool panel left + canvas right ─────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle{background:#3a3f4b;}")

        # Tool panel
        tool_panel = self._build_tool_panel()
        tool_panel.setFixedWidth(220)
        splitter.addWidget(tool_panel)

        # Canvas scroll area
        canvas_scroll = QScrollArea()
        canvas_scroll.setWidgetResizable(True)
        canvas_scroll.setStyleSheet("background:#1e2025;border:none;")

        canvas_container = QWidget()
        canvas_container.setStyleSheet("background:#1e2025;")
        canvas_layout = QVBoxLayout(canvas_container)
        canvas_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        canvas_layout.setContentsMargins(24, 24, 24, 24)

        self._canvas = PageCanvas()
        canvas_layout.addWidget(self._canvas)
        canvas_layout.addStretch()

        canvas_scroll.setWidget(canvas_container)
        splitter.addWidget(canvas_scroll)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter)

        # Connect canvas signals
        self._canvas.point_clicked.connect(self._on_point_click)
        self._canvas.rect_selected.connect(self._on_rect_select)

        # Empty state label
        self._empty_lbl = QLabel("Open a PDF to start editing")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet("color:#5c6370;font-size:15px;")
        canvas_layout.insertWidget(0, self._empty_lbl)
        self._canvas.setVisible(False)

    def _build_tool_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet("background:#252830;border-right:1px solid #3a3f4b;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 14, 12, 14)
        layout.setSpacing(10)

        lbl = QLabel("Annotation Tools")
        lbl.setObjectName("sectionHeader")
        layout.addWidget(lbl)

        # Tool buttons
        tools = [
            ("note",      "📌", "Sticky Note"),
            ("freetext",  "T",  "Free Text"),
            ("highlight", "🟨", "Highlight"),
            ("stamp",     "🔖", "Stamp"),
            ("redact",    "⬛", "Redact"),
        ]
        self._tool_btns: dict[str, QToolButton] = {}
        for key, icon, label in tools:
            btn = QToolButton()
            btn.setText(f"  {icon}  {label}")
            btn.setCheckable(True)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setFixedHeight(36)
            btn.clicked.connect(lambda checked, k=key: self._set_tool(k))
            self._tool_btns[key] = btn
            layout.addWidget(btn)

        # Separator
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background:#3a3f4b;max-height:1px;margin:4px 0;")
        layout.addWidget(sep)

        # Options
        opts_lbl = QLabel("Options")
        opts_lbl.setObjectName("sectionHeader")
        layout.addWidget(opts_lbl)

        # Color picker
        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("Color:"))
        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(32, 24)
        self._color_btn.setStyleSheet(f"background:{self._annot_color.name()};border-radius:3px;")
        self._color_btn.clicked.connect(self._pick_color)
        color_row.addWidget(self._color_btn)
        color_row.addStretch()
        layout.addLayout(color_row)

        # Free text content
        text_lbl = QLabel("Text content:")
        self._text_input = QLineEdit()
        self._text_input.setPlaceholderText("Note text…")
        layout.addWidget(text_lbl)
        layout.addWidget(self._text_input)

        # Font size
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Font size:"))
        self._font_size = QSpinBox()
        self._font_size.setRange(6, 72)
        self._font_size.setValue(12)
        size_row.addWidget(self._font_size)
        size_row.addStretch()
        layout.addLayout(size_row)

        # Stamp type
        stamp_lbl = QLabel("Stamp type:")
        self._stamp_combo = QComboBox()
        for s in ["APPROVED", "DRAFT", "CONFIDENTIAL", "REVIEWED", "VOID", "COPY"]:
            self._stamp_combo.addItem(s)
        layout.addWidget(stamp_lbl)
        layout.addWidget(self._stamp_combo)

        # Separator
        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("background:#3a3f4b;max-height:1px;margin:4px 0;")
        layout.addWidget(sep2)

        # Erase annotations
        erase_btn = QPushButton("🗑  Erase All Annotations")
        erase_btn.setObjectName("dangerButton")
        erase_btn.clicked.connect(self._erase_annotations)
        layout.addWidget(erase_btn)

        layout.addStretch()

        # Set default tool
        self._set_tool("note")
        return panel

    # ------------------------------------------------------------------
    # Tool selection
    # ------------------------------------------------------------------

    def _set_tool(self, key: str) -> None:
        self._active_tool = key
        rect_tools = {"highlight", "redact"}
        self._canvas.set_drag_mode(key in rect_tools)
        for k, btn in self._tool_btns.items():
            btn.setChecked(k == key)

    # ------------------------------------------------------------------
    # Open / Save
    # ------------------------------------------------------------------

    def _open_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF", "", "PDF Files (*.pdf)"
        )
        if not path:
            return
        try:
            if self._doc:
                self._doc.close()
            self._doc = fitz.open(path)
            self._doc_path = path
            self._current_page = 0
            self._page_spin.setMaximum(self._doc.page_count)
            self._page_spin.setValue(1)
            self._total_lbl.setText(f"/ {self._doc.page_count}")
            for w in (self._prev_btn, self._next_btn, self._page_spin, self._save_btn):
                w.setEnabled(True)
            self._canvas.setVisible(True)
            self._empty_lbl.setVisible(False)
            self._render_page()
            self._recent.add(path)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not open PDF:\n{exc}")

    def _save_pdf(self) -> None:
        if not self._doc:
            return
        stem = Path(self._doc_path).stem
        default = unique_path(
            os.path.join(str(Path(self._doc_path).parent), f"{stem}_edited.pdf")
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Edited PDF", default, "PDF Files (*.pdf)"
        )
        if path:
            try:
                self._doc.save(path)
                QMessageBox.information(self, "Saved", f"Saved to:\n{path}")
            except Exception as exc:
                QMessageBox.critical(self, "Error", f"Could not save:\n{exc}")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _prev_page(self) -> None:
        if self._doc and self._current_page > 0:
            self._current_page -= 1
            self._page_spin.blockSignals(True)
            self._page_spin.setValue(self._current_page + 1)
            self._page_spin.blockSignals(False)
            self._render_page()

    def _next_page(self) -> None:
        if self._doc and self._current_page < self._doc.page_count - 1:
            self._current_page += 1
            self._page_spin.blockSignals(True)
            self._page_spin.setValue(self._current_page + 1)
            self._page_spin.blockSignals(False)
            self._render_page()

    def _go_to_page(self, value: int) -> None:
        if self._doc:
            self._current_page = max(0, min(value - 1, self._doc.page_count - 1))
            self._render_page()

    def _zoom_in(self) -> None:
        self._zoom = min(self._zoom + 0.25, 4.0)
        self._zoom_lbl.setText(f"{int(self._zoom * 100)}%")
        self._render_page()

    def _zoom_out(self) -> None:
        self._zoom = max(self._zoom - 0.25, 0.5)
        self._zoom_lbl.setText(f"{int(self._zoom * 100)}%")
        self._render_page()

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def _render_page(self) -> None:
        if not self._doc:
            return
        page = self._doc[self._current_page]
        mat = fitz.Matrix(self._zoom * 2, self._zoom * 2)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = QImage(pix.samples, pix.width, pix.height, pix.stride,
                     QImage.Format.Format_RGB888)
        self._canvas.set_page_pixmap(QPixmap.fromImage(img))

    # ------------------------------------------------------------------
    # Annotation handlers
    # ------------------------------------------------------------------

    def _on_point_click(self, canvas_pt: QPoint) -> None:
        if not self._doc:
            return
        page = self._doc[self._current_page]
        scale = self._zoom * 2
        pt = fitz.Point(canvas_pt.x() / scale, canvas_pt.y() / scale)
        color = self._fitz_color(self._annot_color)

        if self._active_tool == "note":
            text = self._text_input.text() or "Note"
            annot = page.add_text_annot(pt, text)
            annot.set_colors(stroke=color)
            annot.update()

        elif self._active_tool == "freetext":
            text = self._text_input.text() or "Text"
            size = self._font_size.value()
            rect = fitz.Rect(pt.x, pt.y, pt.x + max(len(text) * size * 0.6, 80), pt.y + size + 8)
            annot = page.add_freetext_annot(rect, text, fontsize=size, text_color=color)
            annot.update()

        elif self._active_tool == "stamp":
            stamp_text = self._stamp_combo.currentText()
            page_rect = page.rect
            center = fitz.Point(page_rect.width / 2, page_rect.height / 2)
            # Use a large diagonal free-text as stamp
            rect = fitz.Rect(
                center.x - 140, center.y - 30,
                center.x + 140, center.y + 30,
            )
            annot = page.add_freetext_annot(
                rect, stamp_text,
                fontsize=40, text_color=(0.8, 0.2, 0.2),
                rotate=30,
            )
            annot.update()

        self._render_page()

    def _on_rect_select(self, canvas_rect: QRect) -> None:
        if not self._doc:
            return
        page = self._doc[self._current_page]
        scale = self._zoom * 2
        pdf_rect = fitz.Rect(
            canvas_rect.left()  / scale,
            canvas_rect.top()   / scale,
            canvas_rect.right() / scale,
            canvas_rect.bottom()/ scale,
        )
        color = self._fitz_color(self._annot_color)

        if self._active_tool == "highlight":
            quads = fitz.Quad(pdf_rect)
            annot = page.add_highlight_annot(quads)
            annot.set_colors(stroke=color)
            annot.update()

        elif self._active_tool == "redact":
            page.add_redact_annot(pdf_rect, fill=color)
            page.apply_redactions()

        self._render_page()

    def _erase_annotations(self) -> None:
        if not self._doc:
            return
        reply = QMessageBox.question(
            self, "Erase All Annotations",
            "This will permanently remove all annotations from the current document.\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for page in self._doc:
            for annot in page.annots():
                page.delete_annot(annot)
        self._render_page()
        QMessageBox.information(self, "Done", "All annotations removed.")

    # ------------------------------------------------------------------
    # Color picker
    # ------------------------------------------------------------------

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(self._annot_color, self, "Choose Annotation Color")
        if color.isValid():
            self._annot_color = color
            self._color_btn.setStyleSheet(
                f"background:{color.name()};border-radius:3px;"
            )

    @staticmethod
    def _fitz_color(qc: QColor) -> Tuple[float, float, float]:
        return (qc.redF(), qc.greenF(), qc.blueF())

    # ------------------------------------------------------------------
    # External API
    # ------------------------------------------------------------------

    def preload_files(self, paths: List[str]) -> None:
        if paths:
            self._open_pdf_path(paths[0])

    def _open_pdf_path(self, path: str) -> None:
        """Open a PDF directly without a file dialog."""
        try:
            if self._doc:
                self._doc.close()
            self._doc = fitz.open(path)
            self._doc_path = path
            self._current_page = 0
            self._page_spin.setMaximum(self._doc.page_count)
            self._page_spin.setValue(1)
            self._total_lbl.setText(f"/ {self._doc.page_count}")
            for w in (self._prev_btn, self._next_btn, self._page_spin, self._save_btn):
                w.setEnabled(True)
            self._canvas.setVisible(True)
            self._empty_lbl.setVisible(False)
            self._render_page()
            self._recent.add(path)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not open PDF:\n{exc}")
