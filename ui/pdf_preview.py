"""
Scrollable PDF preview widget powered by PyMuPDF.
"""

from __future__ import annotations

import fitz
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QPushButton,
)


class PDFPreviewWidget(QWidget):
    """Shows one page of a PDF at a time with zoom controls."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._doc: fitz.Document | None = None
        self._current_page = 0
        self._zoom = 1.0
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QWidget(self)
        toolbar.setFixedHeight(42)
        toolbar.setStyleSheet("background: #181825; border-bottom: 1px solid #313244;")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(8, 4, 8, 4)

        self._prev_btn = QPushButton("◀", self)
        self._prev_btn.setFixedWidth(30)
        self._prev_btn.clicked.connect(self._prev_page)

        self._page_spin = QSpinBox(self)
        self._page_spin.setMinimum(1)
        self._page_spin.setFixedWidth(60)
        self._page_spin.valueChanged.connect(self._go_to_page)

        self._total_label = QLabel("/ 0", self)
        self._total_label.setStyleSheet("color: #6c7086;")

        self._next_btn = QPushButton("▶", self)
        self._next_btn.setFixedWidth(30)
        self._next_btn.clicked.connect(self._next_page)

        zoom_out = QPushButton("−", self)
        zoom_out.setFixedWidth(30)
        zoom_out.clicked.connect(self._zoom_out)

        self._zoom_label = QLabel("100%", self)
        self._zoom_label.setFixedWidth(50)
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        zoom_in = QPushButton("+", self)
        zoom_in.setFixedWidth(30)
        zoom_in.clicked.connect(self._zoom_in)

        zoom_fit = QPushButton("Fit", self)
        zoom_fit.setFixedWidth(40)
        zoom_fit.clicked.connect(self._zoom_fit)

        tb_layout.addWidget(self._prev_btn)
        tb_layout.addWidget(self._page_spin)
        tb_layout.addWidget(self._total_label)
        tb_layout.addWidget(self._next_btn)
        tb_layout.addStretch()
        tb_layout.addWidget(zoom_out)
        tb_layout.addWidget(self._zoom_label)
        tb_layout.addWidget(zoom_in)
        tb_layout.addWidget(zoom_fit)

        # Scroll area
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll.setStyleSheet("background: #252537; border: none;")

        self._page_label = QLabel(self)
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_label.setStyleSheet("background: #252537;")
        self._page_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._scroll.setWidget(self._page_label)

        layout.addWidget(toolbar)
        layout.addWidget(self._scroll)

        self._set_controls_enabled(False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_pdf(self, path: str) -> None:
        if self._doc:
            self._doc.close()
        self._doc = fitz.open(path)
        self._current_page = 0
        self._zoom = 1.0
        self._page_spin.setMaximum(self._doc.page_count)
        self._page_spin.setValue(1)
        self._total_label.setText(f"/ {self._doc.page_count}")
        self._set_controls_enabled(True)
        self._render()

    def close_pdf(self) -> None:
        if self._doc:
            self._doc.close()
            self._doc = None
        self._page_label.setPixmap(QPixmap())
        self._set_controls_enabled(False)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _prev_page(self) -> None:
        if self._doc and self._current_page > 0:
            self._current_page -= 1
            self._page_spin.blockSignals(True)
            self._page_spin.setValue(self._current_page + 1)
            self._page_spin.blockSignals(False)
            self._render()

    def _next_page(self) -> None:
        if self._doc and self._current_page < self._doc.page_count - 1:
            self._current_page += 1
            self._page_spin.blockSignals(True)
            self._page_spin.setValue(self._current_page + 1)
            self._page_spin.blockSignals(False)
            self._render()

    def _go_to_page(self, value: int) -> None:
        if self._doc:
            self._current_page = max(0, min(value - 1, self._doc.page_count - 1))
            self._render()

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------

    def _zoom_in(self) -> None:
        self._zoom = min(self._zoom + 0.25, 4.0)
        self._update_zoom_label()
        self._render()

    def _zoom_out(self) -> None:
        self._zoom = max(self._zoom - 0.25, 0.25)
        self._update_zoom_label()
        self._render()

    def _zoom_fit(self) -> None:
        self._zoom = 1.0
        self._update_zoom_label()
        self._render()

    def _update_zoom_label(self) -> None:
        self._zoom_label.setText(f"{int(self._zoom * 100)}%")

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self) -> None:
        if not self._doc:
            return
        page = self._doc[self._current_page]
        mat = fitz.Matrix(self._zoom * 2, self._zoom * 2)  # 2x for retina-like sharpness
        pix = page.get_pixmap(matrix=mat, alpha=False)

        img = QImage(
            pix.samples,
            pix.width,
            pix.height,
            pix.stride,
            QImage.Format.Format_RGB888,
        )
        self._page_label.setPixmap(QPixmap.fromImage(img))

    def _set_controls_enabled(self, enabled: bool) -> None:
        for w in (self._prev_btn, self._next_btn, self._page_spin):
            w.setEnabled(enabled)
